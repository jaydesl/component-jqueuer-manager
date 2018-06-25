# Time string parser
# It parses the values in the experiment file (ex. JSON) and returns the values in seconds.
import sys 

def seconds(value):
	return value

def minutes(value):
	return value * 60

def hours(value):
	return value * 60 * 60

def days(value):
	return value * 60 * 60 * 24

# This is the main function which can be used to convert a simple number of (day, hour or second) to seconds
def get_seconds(text):
	result = 2147483647
	try:
		value = int(text.split("#")[0])
		unit  = text.split("#")[1]

		units = {
			's' : seconds(value),
			'm' : minutes(value),
			'h' : hours(value),
			'd' : days(value),
		}
		result = units[unit]
	except Exception as e:
		pass

	return result