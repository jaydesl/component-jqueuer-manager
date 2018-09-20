from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse, urllib.request, json, time, ast, random, requests
from pprint import pprint
from threading import Thread
from parameters import backend_experiment_db, micado_master_ip

from experiment import Experiment

# Add an experiment
def add_experiment(experiment_json):
	private_id = str(int(round(time.time() * 1000))) + "_" + str(random.randrange(100, 999))
	experiment_id = "exp_" + private_id

	experiment = Experiment(experiment_id, private_id, experiment_json)
	experiment_thread = Thread(target = experiment.start, args = ())
	experiment_thread.start()

	experiments[experiment_id] = {'experiment': experiment, 'thread': experiment_thread}
	return str(experiment_id) + " has been added & started successfully ! \n"

# Delete an experiment
def del_experiment(experiment_json):
	customer_service_name = experiment_json['service_name']
	if (backend_experiment_db.exists(customer_service_name)):
		backend_experiment_db.delete(customer_service_name)
		return "Customer Service " + customer_service_name + " has been removed from the queue" + "\n"
	return "Customer Service " + customer_service_name + " wasn't found in the queue" + "\n"

# Quick prepare tosca
def prep_tosca(private_id):
	service_name = "jq_test_slim__" + private_id
	server_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')

	with open("tosca.yaml", 'w') as newfile:
		with open ("/etc/jqueuer/tosca/jq-tosca.yaml") as template:
			for line in template:
				if 'JQUEUER_IP' in line:
					newfile.write(line.replace("JQUEUER_IP", server_ip))
					continue
				elif 'EXPID' in line:
					newfile.write(line.replace("EXPID", 'exp_'+private_id))
					continue
				newfile.write(line.replace("repast__experiment", service_name))

def submit_tosca():
	url = 'https://admin:admin@' + micado_master_ip + ':443/toscasubmitter/v1.0/app/launch/file/'
	files = {'file': open('tosca.yaml','rb')}
	data = {'id': 'jaydes'}

	r = requests.post(url, files=files, data=data, verify=False)

# HTTP Server Class
class HTTP(BaseHTTPRequestHandler):
	def _set_headers(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

	def do_GET(self):
		# Processing GET requests
		try:
			html_file = open('./index.html','rb')
			response = html_file.read()
			html_file.close()
			self._set_headers()
			self.wfile.write(response)
			return
		except Exception as e:
			pass

	def do_HEAD(self):
		self._set_headers()

	def do_POST(self):
		# Processing POST requests
		content_length= None
		data_json = None
		data =None
		try:
			content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
			data = self.rfile.read(int(content_length)).decode('utf-8')
			data_json = ast.literal_eval(data)
			pass
		except Exception as e:
			print("Error in parsing the content_length and packet data")

		if (self.path == '/experiment/result'):

			html_file = open('./' + data_json['id'] + '.html','a')
			text = '<hr>Received from {} at {}: Params: {} '.format(
				str(self.client_address),
				str(time.time()),
				str(data_json)
			)
			html_file.write(text)
			html_file.close()
			data_back = "received"
		if (self.path == '/experiment/add'):
			data_back = add_experiment(data_json)
			prep_tosca(data_back[4:21])
			submit_tosca()
		elif (self.path == '/experiment/del'):
			data_back = del_experiment(data_json)

		self._set_headers()
		self.wfile.write(bytes(str(data_back), "utf-8"))


def start(experiments_arg, port=8081):
	# Starting the REST API Server
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
