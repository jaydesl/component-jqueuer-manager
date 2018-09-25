from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse, urllib.request, json, time, ast, random, requests
from pprint import pprint
from threading import Thread
from parameters import backend_experiment_db

from experiment import Experiment
import totosca.template

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
	micado_master_ip = experiment_json.get("micado_ip")
	app_id = experiment_json.get("image_url").split("/")[0]

	url = 'https://admin:admin@' + micado_master_ip + \
		  ':443/toscasubmitter/v1.0/app/undeploy/' + app_id

	r = requests.delete(url, verify=False)
	backend_experiment_db.flushall()
	return app_id + " and its infrastructure have been removed ! \n"
	#customer_service_name = experiment_json['service_name']
	#if (backend_experiment_db.exists(customer_service_name)):
	#	backend_experiment_db.delete(customer_service_name)
	#	return "Customer Service " + customer_service_name + " has been removed from the queue" + "\n"
	#return "Customer Service " + customer_service_name + " wasn't found in the queue" + "\n"

# Prepare tosca
def do_tosca(private_id, data_json):
	app_id, app_name = data_json.get("image_url").split("/")
	service_name = app_name.replace("/","_").replace(":","_").replace(".","_").replace("-","_") + "__" + private_id
	jq_server_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
	micado_master_ip = data_json.get("micado_ip")

	manual_entries = {"JQUEUER_IP": jq_server_ip,
					  "EXPID": 'exp_' + private_id,
					  "SERVICE_NAME": service_name}

	jqtosca = totosca.template.Template(data_json, manual_entries)
	jqtosca.maketosca("tosca.yaml")

	url = 'https://admin:admin@' + micado_master_ip + ':443/toscasubmitter/v1.0/app/launch/file/'
	files = {'file': open('tosca.yaml','rb')}
	data = {'id': app_id}

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
		data = None
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
			if data_json.get("micado_ip"):
				data_back = add_experiment(data_json)
				do_tosca(data_back[4:21], data_json)
			else:
				data_back = 'Please specify a "micado_ip" in your .json'
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
