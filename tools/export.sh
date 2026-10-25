#!/usr/bin/env bash
# Exports Wildbound into build/ and collects shareable archives in build/dist/.
# The web export is also copied to public/, the static site Vercel serves.
#   tools/export.sh            # web + windows + linux + macos
#   tools/export.sh web linux  # just these
# Needs Godot 4.7.x with export templates installed (GODOT=/path/to/godot to override).
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT=${GODOT:-godot}
targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(web windows linux macos)

mkdir -p build/dist
touch build/.gdignore   # keep exported files out of the project's import scan
"$GODOT" --headless --path . --import >/dev/null 2>&1 || true

export_preset() {  # preset name, output path
	mkdir -p "$(dirname "$2")"
	echo "== $1 -> $2"
	"$GODOT" --headless --path . --export-release "$1" "$2" > "build/export_$1.log" 2>&1 \
		|| { echo "export '$1' failed, see build/export_$1.log"; tail -n 20 "build/export_$1.log"; exit 1; }
}

for t in "${targets[@]}"; do
	case "$t" in
	web)
		rm -rf build/web
		export_preset Web build/web/index.html
		python3 tools/package_web.py build/web build/web-dist
		# public/ is the committed copy that static hosts (Vercel) serve as-is.
		find public -mindepth 1 ! -name .gdignore -delete 2>/dev/null || true
		mkdir -p public && touch public/.gdignore
		cp build/web-dist/* public/
		;;
	windows)
		rm -rf build/windows
		export_preset Windows build/windows/Wildbound.exe
		(cd build/windows && rm -f ../dist/Wildbound-windows.zip && zip -q -9 ../dist/Wildbound-windows.zip Wildbound.exe)
		;;
	linux)
		rm -rf build/linux
		export_preset Linux build/linux/Wildbound.x86_64
		(cd build/linux && rm -f ../dist/Wildbound-linux.zip && zip -q -9 ../dist/Wildbound-linux.zip Wildbound.x86_64)
		;;
	macos)
		rm -rf build/macos
		export_preset macOS build/macos/Wildbound.zip
		cp build/macos/Wildbound.zip build/dist/Wildbound-macos.zip
		;;
	*)
		echo "unknown target: $t (use web, windows, linux, macos)"; exit 2 ;;
	esac
done
ls -la build/dist
