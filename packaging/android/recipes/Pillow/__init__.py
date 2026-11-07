from pathlib import Path
import shutil
from packaging.version import Version
from pythonforandroid.recipes.Pillow import PillowRecipe as BasePillowRecipe


class PillowRecipe(BasePillowRecipe):
    extra_build_args = ['--no-isolation']
    hostpython_prerequisites = ['setuptools==78.1.1']

    def install_hostpython_prerequisites(self, *args, **kwargs):
        super().install_hostpython_prerequisites(*args, **kwargs)
        metadata = sorted(Path(self._host_recipe.site_dir).glob('setuptools-*.dist-info'),
                          key=lambda path: Version(path.name.removeprefix('setuptools-').removesuffix('.dist-info')))
        for stale in metadata[:-1]:
            shutil.rmtree(stale)


recipe = PillowRecipe()
