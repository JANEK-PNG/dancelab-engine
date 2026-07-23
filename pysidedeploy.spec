[app]
title = DanceLab Host
project_dir = .
input_file = scripts/dancelab_host_app.py
exec_directory = dist/desktop
project_file = dancelab_host.pyproject
icon = /Users/jantrybus/Developer/dancelab-engine/.venv/lib/python3.12/site-packages/PySide6/scripts/deploy_lib/pyside_icon.icns

[python]
python_path = /Users/jantrybus/Developer/dancelab-engine/.venv/bin/python3.12
packages = Nuitka==4.0
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Core,DBus,Gui,Widgets
plugins = accessiblebridge,egldeviceintegrations,generic,iconengines,imageformats,platforminputcontexts,platforms,platforms/darwin,platformthemes,styles,wayland-decoration-client,wayland-graphics-integration-client,wayland-shell-integration,xcbglintegrations

[android]
wheel_pyside = 
wheel_shiboken = 
plugins = 

[nuitka]
macos.permissions = 
mode = standalone
extra_args = --quiet --noinclude-qt-translations --disable-ccache --nofollow-import-to=torch,demucs,pandas,sklearn,matplotlib,plotly --noinclude-numba-mode=nofollow --module-parameter=numba-disable-jit=yes

[buildozer]
mode = debug
recipe_dir = 
jars_dir = 
ndk_path = 
sdk_path = 
local_libs = 
arch = 
