import time, math, datetime, random
from parameters import backend_experiment_db, JOB_QUEUE_PREFIX
from celery import subtask
import monitoring, job_operations, time_decoder
import docker_agent

class Experiment:
	def __init__(self, experiment_id, private_id, experiment):
		self.log = ""
		self.experiment_actual_start_timestamp	= 	self.time_now()

		self.experiment_id 	= experiment_id
		print("**********************************")
		print(str(experiment_id))
		print(str(private_id))
		print(str(experiment))
		print("**********************************")
		self.image_url = experiment['image_url']
		try:
			self.service_name 	= self.image_url.replace("/","_").replace(":","_").replace(".","_").replace("-","_") + "__" + private_id
			self.add_service(self.service_name)
		except Exception as e:
			self.service_name 	= None
		self.experiment = experiment
		monitoring.experiment_actual_start_timestamp(self.experiment_id, self.service_name, self.experiment_actual_start_timestamp)

	def add_log(self, text):
		if (text):
			self.log += text
			self.log += "\n"

	def time_now(self):
		return datetime.datetime.now().timestamp()

	def add_service(self, service_name):
		if (backend_experiment_db.exists(service_name)):
			return ""
		backend_experiment_db.set(service_name, 
			{'experiment_id':self.experiment_id})
		output = "A new service has just been added " + service_name + "\n"
		self.add_log(output)

	def init_counters(self):
		self.service_replicas_running 				=	0
		self.jqueuer_worker_count 					=	0

		self.jqueuer_task_added_count				= 	0 
		self.jqueuer_task_running_count				=	0
		self.jqueuer_task_started_count				=	0
		self.jqueuer_task_accomplished_count		=	0
		self.jqueuer_task_accomplished_latency		=	0
		self.jqueuer_task_accomplished_latency_count=	0
		self.jqueuer_task_accomplished_latency_sum	=	0

		self.jqueuer_job_added_count				=	0
		self.jqueuer_job_running_count				=	0
		self.jqueuer_job_started_count				=	0
		self.jqueuer_job_accomplished_count			=	0
		self.jqueuer_job_accomplished_latency		=	0
		self.jqueuer_job_accomplished_latency_count	=	0
		self.jqueuer_job_accomplished_latency_sum	=	0

		self.task_per_job_avg						=	0

		self.jqueuer_job_failed_count				=	0
		self.jqueuer_job_failed_latency				=	0
		self.jqueuer_job_failed_latency_count		=	0
		self.jqueuer_job_failed_latency_sum			=	0
		self.reserve_memory							=	0
		self.reserve_cpu							=	0

	def update(self, query_var, result):
		if (result['value'][1] == "NaN"):
			return
		if (query_var == 'jqueuer_task_added_count'):
			#self.jqueuer_task_added_count = int(result['value'][1])
			pass
		elif (query_var == 'jqueuer_task_running_count'):
			self.jqueuer_task_running_count = int(result['value'][1])
		elif (query_var == 'jqueuer_task_started_count'):
			self.jqueuer_task_started_count = int(result['value'][1])
		elif (query_var == 'jqueuer_task_accomplished_count'):
			self.jqueuer_task_accomplished_count = int(result['value'][1])
		elif (query_var == 'jqueuer_task_accomplished_latency'):
			self.jqueuer_task_accomplished_latency = float(result['value'][1])
		elif (query_var == 'jqueuer_task_accomplished_latency_count'):
			self.jqueuer_task_accomplished_latency_count = int(result['value'][1])
		elif (query_var == 'jqueuer_task_accomplished_latency_sum'):
			self.jqueuer_task_accomplished_latency_sum = float(result['value'][1])
		elif (query_var == 'jqueuer_job_running_count'):
			self.jqueuer_job_running_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_started_count'):
			self.jqueuer_job_started_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_count'):
			self.jqueuer_job_accomplished_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_latency'):
			self.jqueuer_job_accomplished_latency = float(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_latency_count'):
			self.jqueuer_job_accomplished_latency_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_latency_sum'):
			self.jqueuer_job_accomplished_latency_sum = float(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_count'):
			self.jqueuer_job_failed_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_latency'):
			self.jqueuer_job_failed_latency = float(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_latency_count'):
			self.jqueuer_job_failed_latency_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_latency_sum'):
			self.jqueuer_job_failed_latency_sum = float(result['value'][1])
		elif (query_var == 'jqueuer_worker_count'):
			if (result['metric']['service_name'] == self.service_name):
				self.jqueuer_worker_count = int(result['value'][1])

	def process_jobs(self):
		output = ""
		if (isinstance(self.experiment['jobs'], list)):
			output = self.process_job_list()
		else:
			output = self.process_job_array()
		self.task_per_job_avg = math.ceil(self.jqueuer_task_added_count / self.jqueuer_job_added_count)
		self.add_log(output)

	def get_task_count(self, tasks):
		count = 0
		try:
			if (isinstance(tasks, list)):
				count = len(tasks)
			else:
				count = tasks['count']
		except Exception as e:
			count = 0
		return count 

	def process_job_list(self):
		self.add_log("There is a list of " + str(len(self.experiment['jobs'])))
		for job in self.experiment['jobs']:
			try:
				job_params = job['params'] 
			except Exception as e:
				job['params'] = self.experiment['params'] 
			try:
				job_command = job['command'] 
			except Exception as e:
				job['command'] = self.experiment['command']

			output = self.add_job(job)
			self.add_log(output)

	def process_job_array(self):
		jobs = self.experiment['jobs']
		print("There is an array of " + str(jobs['count']))
		try:
			job_params = jobs['params'] 
		except Exception as e:
			jobs['params'] = self.experiment['params'] 
		try:
			job_command = jobs['command'] 
		except Exception as e:
			jobs['command'] = self.experiment['command']

		for x in range(0,jobs['count']):
			job_id = jobs['id'] + "_" + str(x)
			output = self.add_job(jobs, job_id)
			self.add_log(output)

	def add_tasks(self, tasks, job_id):
		for task in tasks:
			self.jqueuer_task_added_count += 1
			monitoring.add_task(self.experiment_id, self.service_name, job_id, task['id'])
			self.add_log("The task {} of job {} has been added to monitoring".
				format(str(task['id']), str(job_id)) )

	def add_job(self, job, job_id = None):
		if (not job_id):
			job_id = job["id"]

		self.add_tasks(job['tasks'], job_id)

		self.jqueuer_job_added_count += 1 
		monitoring.add_job(self.experiment_id, self.service_name, job_id)

		job_queue_id = "j_" + self.service_name +"_" + str(int(round(time.time() * 1000))) + "_" + str(random.randrange(100, 999))

		chain = subtask('job_operations.add', queue = JOB_QUEUE_PREFIX + self.service_name)
		chain.delay(self.experiment_id, job_queue_id, job)

		self.add_log("The job_id {} ,job_queue_id: {} - ,JOB_QUEUE_PREFIX: {}has just been added".
			format(str(job_id), str(job_queue_id), str(JOB_QUEUE_PREFIX)))

	def update_params(self):
		self.deadline				=	time_decoder.get_seconds(self.experiment['experiment_deadline'])

		self.experiment_deadline_timestamp		= 	self.experiment_actual_start_timestamp + self.deadline
		monitoring.experiment_deadline_timestamp(self.experiment_id, self.service_name, self.experiment_deadline_timestamp)

		self.service_replicas_min = int(self.experiment['replica_min'])
		monitoring.service_replicas_min(self.experiment_id, self.service_name, self.service_replicas_min)

		self.service_replicas_max = int(self.experiment['replica_max'])
		monitoring.service_replicas_max(self.experiment_id, self.service_name, self.service_replicas_max)

		self.single_task_duration	=	time_decoder.get_seconds(self.experiment['single_task_duration'])
		monitoring.single_task_duration(self.experiment_id, self.service_name, self.single_task_duration)

		self.reserve_memory = self.experiment['reserve_memory']
		self.reserve_cpu 	= self.experiment['reserve_cpu']
		'''
		self.all_job_duration		=	self.single_task_duration * self.jqueuer_task_added_count
		self.estimated_deadline				=	self.single_task_duration * self.jqueuer_task_added_count
		self.estimated_deadline_timestamp	=	self.experiment_actual_start_timestamp + self.estimated_deadline
		'''

	def update_service_replicas_running(self):
		self.service_replicas_running = docker_agent.replicas(self.service_name)
		monitoring.service_replicas_running(self.experiment_id, self.service_name, self.service_replicas_running)

	def calc_replica_count(self):
		self.update_service_replicas_running()
		#jobs_running_count = self.jqueuer_job_started_count - self.jqueuer_job_accomplished_count - self.jqueuer_job_failed_count
		jobs_queued = self.jqueuer_job_added_count - self.jqueuer_job_accomplished_count

		time_remaining	=	self.experiment_deadline_timestamp - self.time_now()

		if (self.jqueuer_task_accomplished_latency == 0):
			self.system_calculated_single_task_duration = self.single_task_duration
		else:
			self.system_calculated_single_task_duration = self.jqueuer_task_accomplished_latency
		monitoring.single_task_duration(self.experiment_id, self.service_name, self.system_calculated_single_task_duration)

		service_replicas_needed = 0
		if (time_remaining > 0):
			service_replicas_needed	= 	(jobs_queued * self.system_calculated_single_task_duration * self.task_per_job_avg) / time_remaining
		else:
			service_replicas_needed	= 	(jobs_queued * self.system_calculated_single_task_duration * self.task_per_job_avg)
		
		service_replicas_needed	= 	math.ceil(service_replicas_needed)

		if (service_replicas_needed > jobs_queued):
			service_replicas_needed = jobs_queued

		monitoring.service_replicas_needed(self.experiment_id, self.service_name, service_replicas_needed)

		if (service_replicas_needed > self.service_replicas_running):
			if (service_replicas_needed > self.service_replicas_max):
				service_replicas_needed = self.service_replicas_max
		else:
			if (service_replicas_needed < self.service_replicas_min):
				service_replicas_needed = self.service_replicas_min
		return service_replicas_needed, time_remaining

	def run_service(self, service_replicas_needed):
		stop_grace_period = str(math.ceil(self.single_task_duration * 1.1)) + "s"
		docker_agent.create(self.image_url, self.service_name, service_replicas_needed, stop_grace_period, self.reserve_memory,self.reserve_cpu)

	def scale(self, service_replicas_needed):
		docker_agent.scale(self.service_name, service_replicas_needed)

	def remove(self):
		docker_agent.remove(self.service_name)

	def start(self):
		self.init_counters()
		self.process_jobs()
		self.update_params()
		service_replicas_needed, time_remaining = self.calc_replica_count()
		self.run_service(service_replicas_needed)
		while self.jqueuer_job_accomplished_count < self.jqueuer_job_added_count:
			monitoring.experiment_running_timestamp(self.experiment_id, self.service_name, time.time())
			service_replicas_needed, time_remaining = self.calc_replica_count()
			print('\nTasks: {} added/{} done|  Jobs: {} added/{} started/{} done/{} failed \n Avg {} Task/Job | Container {} running/{} needed \n Time: {} Remaining/ Single : {} Estimated/ {} Calculated'.
				format(
					str(self.jqueuer_task_added_count), str(self.jqueuer_task_accomplished_count), 
					str(self.jqueuer_job_added_count) , str(self.jqueuer_job_started_count) ,str(self.jqueuer_job_accomplished_count) , str(self.jqueuer_job_failed_count), 
					str(self.task_per_job_avg),
					str(self.service_replicas_running), str(service_replicas_needed),  
					str(time_remaining), str(self.single_task_duration), str(self.system_calculated_single_task_duration)
					))

			if (service_replicas_needed != self.service_replicas_running):
				self.scale(service_replicas_needed)
		else:
			monitoring.experiment_actual_end_timestamp(self.experiment_id, self.service_name, time.time())
			print("--------- Yupppppi, I finished ({} tasks)/({} jobs) in ({} seconds) ----------- ".
				format(str(self.jqueuer_task_added_count), str(self.jqueuer_job_added_count), str(self.time_now() - self.experiment_actual_start_timestamp)))
			self.scale(0)
			self.update_service_replicas_running()
			self.remove()