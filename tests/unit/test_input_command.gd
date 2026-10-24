extends WBTestCase
## Input commands are the network contract: encoding must be lossless for
## everything the simulation reads.


func test_encode_decode_round_trip() -> void:
	var c := InputCommand.new()
	c.tick = 123456
	c.sequence = 987
	c.move_dir = 5
	c.set_aim(Vector2(0.3, -0.8), 6.25)
	c.held = InputCommand.GUARD | InputCommand.ABILITY_3
	c.pressed = InputCommand.ABILITY_3
	c.axis_hint = Cardinal.AXIS_VERTICAL
	var bytes := c.encode()
	assert_le(float(bytes.size()), 20.0, "compact (%d bytes)" % bytes.size())
	var d := InputCommand.decode(bytes)
	assert_eq(d.tick, c.tick, "tick")
	assert_eq(d.sequence, c.sequence, "sequence")
	assert_eq(d.move_dir, c.move_dir, "move")
	assert_near(d.aim.angle_to(c.aim), 0.0, 0.0001, "aim (quantized identically)")
	assert_near(d.aim_distance, 6.25, 0.0001, "aim distance")
	assert_eq(d.held, c.held, "held")
	assert_eq(d.pressed, c.pressed, "pressed")
	assert_eq(d.axis_hint, c.axis_hint, "axis hint")


func test_no_move_and_no_aim_survive_encoding() -> void:
	var c := InputCommand.new()
	var d := InputCommand.decode(c.encode())
	assert_eq(d.move_dir, -1, "no move")
	assert_eq(d.aim, Vector2.ZERO, "no aim")
	assert_eq(d.axis_hint, Cardinal.AXIS_UNKNOWN, "no hint")


func test_eight_way_vectors_are_unit_length() -> void:
	for i in 8:
		assert_near(CombatConst.dir8_to_vec(i).length(), 1.0, 0.000001, "dir %d" % i)
	assert_eq(CombatConst.vec_to_dir8(Vector2(1, 1)), 1, "SE")
	assert_eq(CombatConst.vec_to_dir8(Vector2(0, -1)), 6, "N")
	assert_eq(CombatConst.vec_to_dir8(Vector2(0.05, 0.05)), -1, "deadzone")


func test_input_buffer_window() -> void:
	var b := InputBuffer.new()
	b.record(InputCommand.DASH, 10)
	assert_true(b.has(InputCommand.DASH, 10 + CombatConst.INPUT_BUFFER_TICKS), "within window")
	assert_false(b.has(InputCommand.DASH, 11 + CombatConst.INPUT_BUFFER_TICKS), "expired")
	b.consume(InputCommand.DASH)
	assert_false(b.has(InputCommand.DASH, 11), "consumed once")
