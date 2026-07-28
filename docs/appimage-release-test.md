# PaperTranslate AppImage Release Test

## Release Summary

- Package type: AppImage
- Architecture: x86_64
- AppImage filename: `PaperTranslate-x86_64.AppImage`
- Approximate size: 6.7 GB
- Bundled Python: CPython 3.10.20
- Test environment: Ubuntu with NVIDIA GeForce RTX 3060 12 GB
- Branch: `thai-bundled-python-runtime`
- Runtime strategy: staged OCR and translation because both models cannot run concurrently within 12 GB VRAM

## Build Result

The AppImage was generated successfully using `appimagetool`.

```text
Success
Final AppImage build: PASS
cd ~/Paper-Translate-Personal-Project

cat > docs/appimage-release-test.md <<'EOF'
# PaperTranslate AppImage Release Test

## Release Summary

- Package type: AppImage
- Architecture: x86_64
- AppImage filename: `PaperTranslate-x86_64.AppImage`
- Approximate size: 6.7 GB
- Bundled Python: CPython 3.10.20
- Test environment: Ubuntu with NVIDIA GeForce RTX 3060 12 GB
- Branch: `thai-bundled-python-runtime`
- Runtime strategy: staged OCR and translation because both models cannot run concurrently within 12 GB VRAM

## Build Result

The AppImage was generated successfully using `appimagetool`.

```text
Success
Final AppImage build: PASS
