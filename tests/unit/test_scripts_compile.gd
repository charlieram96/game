extends WBTestCase
## Every script in the project must compile. A parse error otherwise only
## shows up when its scene happens to load.

const ROOTS := ["res://scripts", "res://scenes", "res://tests"]


func test_all_scripts_compile() -> void:
	var count := 0
	for root in ROOTS:
		for path in _collect(root):
			var s: Variant = load(path)
			count += 1
			if s == null or not (s as GDScript).can_instantiate():
				fail("does not compile: %s" % path)
	assert_gt(float(count), 60.0, "found the project's scripts (%d)" % count)


func test_all_shaders_load() -> void:
	for path in _collect("res://shaders", ".gdshader"):
		var sh: Shader = load(path)
		assert_true(sh != null and sh.code != "", "shader loads: %s" % path)


func _collect(dir: String, ext: String = ".gd") -> Array[String]:
	var out: Array[String] = []
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		if f.ends_with(ext):
			out.append(dir.path_join(f))
	for sub in d.get_directories():
		out.append_array(_collect(dir.path_join(sub), ext))
	return out
