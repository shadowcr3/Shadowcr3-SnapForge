#!/usr/bin/env bash
# Builds the Linux SnapForge package and strips Qt components verified (via
# ldd against the actual built binaries) to be unreferenced by anything
# this application loads. See packaging/BUILD.md for the full writeup.
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf build dist snapforge.spec

pyinstaller --noconfirm --windowed \
  --name snapforge \
  --paths src \
  src/snapforge/main.py

QT_DIR="dist/snapforge/_internal/PySide6/Qt"

# Verified via `ldd` against libQt6Gui/Widgets/XcbQpa/libqxcb.so in this
# repo's own built output: the only Qt shared libraries actually
# hard-linked are Core, Gui, Widgets, DBus, and XcbQpa. Everything removed
# below is unreferenced by that dependency graph.
rm -f \
  "$QT_DIR/lib/libQt6Quick.so.6" \
  "$QT_DIR/lib/libQt6Qml.so.6" \
  "$QT_DIR/lib/libQt6QmlModels.so.6" \
  "$QT_DIR/lib/libQt6QmlMeta.so.6" \
  "$QT_DIR/lib/libQt6QmlWorkerScript.so.6" \
  "$QT_DIR/lib/libQt6Pdf.so.6" \
  "$QT_DIR/lib/libQt6VirtualKeyboard.so.6" \
  "$QT_DIR/lib/libQt6VirtualKeyboardQml.so.6" \
  "$QT_DIR/lib/libQt6WaylandClient.so.6" \
  "$QT_DIR/lib/libQt6WlShellIntegration.so.6" \
  "$QT_DIR/lib/libQt6Network.so.6" \
  "$QT_DIR/lib/libQt6OpenGL.so.6" \
  "$QT_DIR/lib/libQt6Svg.so.6" \
  "$QT_DIR/lib/libQt6EglFSDeviceIntegration.so.6" \
  "$QT_DIR/lib/libQt6EglFsKmsSupport.so.6"

rm -rf \
  "$QT_DIR/plugins/wayland-decoration-client" \
  "$QT_DIR/plugins/wayland-graphics-integration-client" \
  "$QT_DIR/plugins/wayland-shell-integration" \
  "$QT_DIR/plugins/egldeviceintegrations" \
  "$QT_DIR/plugins/platforminputcontexts" \
  "$QT_DIR/translations" \
  "$QT_DIR/plugins/imageformats"

echo "Built and trimmed: $(du -sh dist/snapforge | cut -f1)"
echo "Running self-test against the trimmed binary..."
# --self-test never shows a window, so QT_QPA_PLATFORM=offscreen is enough
# here — no real/virtual display needed, unlike an interactive launch.
env -i PATH=/usr/bin:/bin HOME="${HOME:-/root}" QT_QPA_PLATFORM=offscreen \
  ./dist/snapforge/snapforge --self-test

VERSION=$(python3 -c "import sys; sys.path.insert(0, 'src'); import snapforge; print(snapforge.__version__)")
ZIP_NAME="SnapForge-v${VERSION}-linux.zip"
rm -f "$ZIP_NAME"
(cd dist && zip -rq "../$ZIP_NAME" snapforge)
echo "Done: $ZIP_NAME"
