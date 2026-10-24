extends SceneTree
## Headless test runner.
##
##   godot --headless --path . -s res://tests/run_tests.gd
##   godot --headless --path . -s res://tests/run_tests.gd -- --filter=dash
##
## Discovers tests/unit/test_*.gd and tests/integration/test_*.gd; runs every
## `test_*` method; exits with code 1 if anything fails.

const DIRS := ["res://tests/unit", "res://tests/integration"]


func _init() -> void:
	# Run after the tree (and autoloads) are ready.
	process_frame.connect(_run, CONNECT_ONE_SHOT)


func _run() -> void:
	var filter := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--filter="):
			filter = arg.substr(9)
	var total := 0
	var failed := 0
	var failed_names: Array[String] = []
	var started := Time.get_ticks_msec()
	for dir in DIRS:
		for path in _list(dir):
			var script: GDScript = load(path)
			if script == null or not script.can_instantiate():
				print("  [LOAD ERROR] ", path)
				failed += 1
				failed_names.append(path)
				continue
			var methods: Array[String] = []
			for m in script.get_script_method_list():
				var mname: String = m["name"]
				if mname.begins_with("test_") and not methods.has(mname):
					methods.append(mname)
			methods.sort()
			var file_label: String = path.get_file().get_basename()
			for mname in methods:
				if filter != "" and not (file_label + "." + mname).contains(filter):
					continue
				var inst: WBTestCase = script.new()
				inst._begin(mname)
				inst.before_each()
				var t0 := Time.get_ticks_usec()
				# Tests may be coroutines (await); call() returns the result either way.
				var ret: Variant = inst.call(mname)
				if ret is Object and ret.has_method("is_valid"):
					await ret
				inst.after_each()
				var ms := float(Time.get_ticks_usec() - t0) / 1000.0
				total += 1
				var fails := inst.failures()
				if fails.is_empty():
					print("  ok    %s.%s (%.1f ms)" % [file_label, mname, ms])
				else:
					failed += 1
					failed_names.append(file_label + "." + mname)
					print("  FAIL  %s.%s" % [file_label, mname])
					for f in fails:
						print("          - ", f)
	var secs := float(Time.get_ticks_msec() - started) / 1000.0
	print("")
	print("%d tests, %d failed (%.2f s)" % [total, failed, secs])
	if failed > 0:
		print("Failed: ", ", ".join(failed_names))
	quit(1 if failed > 0 else 0)


func _list(dir: String) -> Array[String]:
	var out: Array[String] = []
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		if f.begins_with("test_") and f.ends_with(".gd"):
			out.append(dir.path_join(f))
	out.sort()
	return out
