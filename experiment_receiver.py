from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse, json, time, ast, random
from pprint import pprint
from threading import Thread

from experiment import Experiment

def add_experiment(experiment_json):
	print("-------------------------------------------")
	print(str(experiments))
	print("-------------------------------------------")
	output = "experiment_json: " + str(experiment_json)
	private_id = str(int(round(time.time() * 1000))) + "_" + str(random.randrange(100, 999))
	experiment_id = "exp_" + private_id

	experiment = Experiment(experiment_id, private_id, experiment_json)
	experiment_thread = Thread(target = experiment.start, args = ())
	experiment_thread.start()

	experiments[experiment_id] = {'experiment': experiment, 'thread': experiment_thread}
	print(output)
	return str(experiment_id) + " has been added & started successfully ! \n"

def del_experiment(experiment_json):
	customer_service_name = experiment_json['service_name']
	if (backend_experiment_db.exists(customer_service_name)):
		backend_experiment_db.delete(customer_service_name)
		return "Customer Service " + customer_service_name + " has been removed from the queue" + "\n"
	return "Customer Service " + customer_service_name + " wasn't found in the queue" + "\n"

class HTTP(BaseHTTPRequestHandler):
	def _set_headers(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

	def do_GET(self):
		data = None
		binary = None
		response = "Error 404"
		try:
			html_file = open('.' + self.path + '.html','r')
			response = html_file.read()
			html_file.close()
		except Exception as e:
			pass
		binary = bytes(json.dumps(response),"utf-8")
		self._set_headers()
		self.wfile.write(binary)

	def do_HEAD(self):
		self._set_headers()
		
	def do_POST(self):
		#pprint(vars(self))
		# Doesn't do anything with posted data
		content_length= None
		data_json = None
		data =None
		try:
			content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
			data = self.rfile.read(int(content_length)).decode('utf-8')
			print('data : ' + str(data))
			data_json = ast.literal_eval(data)
			#print(data_json['service_name'])
			pass
		except Exception as e:
			print("Error in parsing the content_length and packet data")
		data_back = ""

		if (self.path == '/experiment/result'):

			#data_json = json.load(data)
			print('data_json' + str(data_json))
			html_file = open('./' + data_json['id'] + '.html','a')
			text = '<hr>Received from {} at {}: Params: {} '.format(
				str(self.client_address),
				str(time.time()),
				str(data_json)
			)
			html_file.write(text)
			html_file.close()
			data_back = "received"
			print("------------------/experiment/result---------------")
		if (self.path == '/experiment/add'):
			print(str(data_json))
			data_back = add_experiment(data_json)
			print("------------------/experiment/add---------------")
		elif (self.path == '/experiment/del'):
			print(str(data_json))
			data_back = del_experiment(data_json)
			print("------------------/experiment/del---------------")
		
		self._set_headers()
		self.wfile.write(bytes(str(data_back), "utf-8"))


def start(experiments_arg, port=8081):
	global experiments
	experiments = experiments_arg
	server_address = ('', port)
	httpd = HTTPServer(server_address, HTTP)
	print('Starting Experiment Manager HTTP Server...' + str(port))
	
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		print("***** Error in Experiment Manager HTTP Server *****")
		pass

	httpd.server_close()
	print(time.asctime(), "Experiment Manager Server Stopped - %s:%s" % (server_address, port))
