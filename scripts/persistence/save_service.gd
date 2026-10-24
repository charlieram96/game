extends Node
## Local save/load (autoload "SaveService").
##
## Writes JSON atomically (temp file + rename) so a crash mid-save can't
## corrupt the save. Online builds will replace this with server-owned
## persistence; PlayerProfile.to_dict() is the shared schema.

const DEFAULT_PATH := "user://wildbound_save.json"

var path: String = DEFAULT_PATH
var profile: PlayerProfile = null


func has_save() -> bool:
	return FileAccess.file_exists(path)


func new_profile(player_name: String) -> PlayerProfile:
	profile = PlayerProfile.new()
	profile.player_name = player_name.strip_edges().substr(0, 16) if player_name.strip_edges() != "" else "Wren"
	profile.created_unix = int(Time.get_unix_time_from_system())
	return profile


func save() -> bool:
	if profile == null:
		return false
	return write_profile(profile, path)


func load_profile() -> bool:
	var p := read_profile(path)
	if p == null:
		return false
	profile = p
	return true


func delete_save() -> void:
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path) if path.begins_with("user://") else path)


static func write_profile(p: PlayerProfile, file_path: String) -> bool:
	var tmp := file_path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_error("Save failed: %s" % FileAccess.get_open_error())
		return false
	f.store_string(JSON.stringify(p.to_dict(), "\t"))
	f.close()
	var abs_tmp := ProjectSettings.globalize_path(tmp)
	var abs_dst := ProjectSettings.globalize_path(file_path)
	if FileAccess.file_exists(file_path):
		DirAccess.remove_absolute(abs_dst)
	return DirAccess.rename_absolute(abs_tmp, abs_dst) == OK


static func read_profile(file_path: String) -> PlayerProfile:
	if not FileAccess.file_exists(file_path):
		return null
	var text := FileAccess.get_file_as_string(file_path)
	var data: Variant = JSON.parse_string(text)
	if not data is Dictionary:
		push_warning("Save file is corrupt: %s" % file_path)
		return null
	return PlayerProfile.from_dict(data)
