#!/usr/bin/env bash
# Publishes a new release: checks the repo, runs the tests, sets APP_VERSION, opens an editor for the
# release notes, then commits, tags vX.Y.Z and pushes. GitHub Actions builds Windows, Linux and Android
# and publishes them under Releases. Linux version of release.ps1.
script="$(realpath "$0")"
cd "$(dirname "$script")/.."
source tools/linux-env.sh "$script" "$@"

RED=$'\e[31m'; GREEN=$'\e[32m'; RESET=$'\e[0m'

stop_release() {
	echo "${RED}$1${RESET}"
	pause
	exit 1
}

run_git() {
	local output
	if ! output="$(git "$@" 2>&1)"; then
		stop_release "git $* failed:"$'\n'"$output"
	fi
	printf '%s' "$output"
}

# True if version $1 is newer than version $2
is_newer() {
	[ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n1)" = "$1" ]
}

identity_file="src/app_identity.py"
current_version="$(sed -n -E "s/^APP_VERSION = '([^']*)'.*/\1/p" "$identity_file" | head -n1)"
# The newest of all release tags and the version in the code
latest_version="$( { git tag --list; echo "$current_version"; } \
	| sed -n -E 's/^v?\.?([0-9]+\.[0-9]+\.[0-9]+)$/\1/p' | sort -V | tail -n1)"
[ -n "$latest_version" ] || latest_version="0.0.0"
IFS=. read -r major minor patch <<< "$latest_version"
suggested="$major.$minor.$((patch + 1))"

echo "Latest release: $latest_version"
version="${1:-}"
if [ -z "$version" ]; then
	read -rp "New version (Enter for $suggested): " version
	[ -n "$version" ] || version="$suggested"
fi
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || stop_release "Version must look like 1.2.3, got '$version'."
is_newer "$version" "$latest_version" || stop_release "Version $version must be newer than $latest_version."
tag="v$version"

[ -z "$(run_git status --porcelain)" ] || stop_release "You have uncommitted changes. Commit or stash them first."
branch="$(run_git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || stop_release "Releases are made from main, but you are on '$branch'."
run_git fetch origin main --tags >/dev/null
[ "$(run_git rev-list --count 'HEAD..origin/main')" = "0" ] || stop_release "GitHub has commits you do not have. Pull first."
[ -z "$(run_git tag --list "$tag")" ] || stop_release "Tag $tag already exists."

echo "Running tests..."
python=".venv-linux/bin/python"
python_works "$python" || python="python3"
QT_QPA_PLATFORM=offscreen "$python" scripts/test.py || stop_release "Tests failed. Nothing was released."

notes_file="docs/release-notes/$version.md"
mkdir -p "$(dirname "$notes_file")"
[ -f "$notes_file" ] || : > "$notes_file"

# Open the release notes in an editor and wait for it to close
if [ -n "${VISUAL:-${EDITOR:-}}" ]; then
	editor=(${VISUAL:-$EDITOR})
elif command -v kate >/dev/null; then
	editor=(kate --block)
elif command -v code >/dev/null; then
	editor=(code --wait)
else
	editor=(nano)
fi
echo "Write what changed in $version, then save and close the editor."
"${editor[@]}" "$notes_file"

if [ -z "$(tr -d '[:space:]' < "$notes_file")" ]; then
	rm -f "$notes_file"
	stop_release "The release notes are empty. Nothing was released."
fi

sed -i -E "s/^APP_VERSION = '[^']*'/APP_VERSION = '$version'/" "$identity_file"

echo "Releasing $tag..."
run_git add -- "$identity_file" "$notes_file" >/dev/null
run_git commit -m "Release $version" >/dev/null
run_git tag -a "$tag" -m "Album Drive $version" >/dev/null
run_git push --atomic origin main "$tag" >/dev/null
echo "${GREEN}Done. GitHub is now building $tag; the release appears under Releases when all builds pass.${RESET}"
pause
