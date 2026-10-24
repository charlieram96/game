class_name WBTestCase
extends RefCounted
## Minimal test base class (no addon dependency). Every method starting with
## `test_` is run by tests/run_tests.gd. Assertions record failures and keep
## going so one run reports everything.

var _failures: Array[String] = []
var _current_test: String = ""


func before_each() -> void:
	pass


func after_each() -> void:
	pass


func _begin(test_name: String) -> void:
	_current_test = test_name
	_failures.clear()


func failures() -> Array[String]:
	return _failures


func fail(message: String) -> void:
	_failures.append(message)


func assert_true(condition: bool, message: String = "expected true") -> void:
	if not condition:
		fail(message)


func assert_false(condition: bool, message: String = "expected false") -> void:
	if condition:
		fail(message)


func assert_eq(actual: Variant, expected: Variant, message: String = "") -> void:
	if typeof(actual) != typeof(expected) and not (_is_num(actual) and _is_num(expected)):
		fail("%s: expected %s (%s) but got %s (%s)" % [message, expected, type_string(typeof(expected)), actual, type_string(typeof(actual))])
	elif actual != expected:
		fail("%s: expected %s but got %s" % [message, expected, actual])


func assert_ne(actual: Variant, unexpected: Variant, message: String = "") -> void:
	if actual == unexpected:
		fail("%s: did not expect %s" % [message, unexpected])


func assert_near(actual: float, expected: float, epsilon: float, message: String = "") -> void:
	if absf(actual - expected) > epsilon:
		fail("%s: expected %.4f ± %.4f but got %.4f" % [message, expected, epsilon, actual])


func assert_gt(actual: float, bound: float, message: String = "") -> void:
	if not (actual > bound):
		fail("%s: expected > %s but got %s" % [message, bound, actual])


func assert_ge(actual: float, bound: float, message: String = "") -> void:
	if not (actual >= bound):
		fail("%s: expected >= %s but got %s" % [message, bound, actual])


func assert_lt(actual: float, bound: float, message: String = "") -> void:
	if not (actual < bound):
		fail("%s: expected < %s but got %s" % [message, bound, actual])


func assert_le(actual: float, bound: float, message: String = "") -> void:
	if not (actual <= bound):
		fail("%s: expected <= %s but got %s" % [message, bound, actual])


func _is_num(v: Variant) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT
