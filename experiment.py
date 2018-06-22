import time, math, datetime, random
from parameters import backend_experiment_db, JOB_QUEUE_PREFIX
from celery import subtask
import monitoring, job_operations, time_decoder
import docker_agent

class Experiment:
	def __init__(self, experiment_id, private_id, experiment):
		self.experiment_actual_start_timestamp	= 	self.time_now()

		self.experiment_id 	= experiment_id
		self.image_url = experiment['image_url']
		try:
			self.service_name 	= self.image_url.replace("/","_").replace(":","_").replace(".","_").replace("-","_") + "__" + private_id
			self.add_service(self.service_name)
		except Exception as e:
			self.service_name 	= None
		self.experiment = experiment
		monitoring.experiment_actual_start_timestamp(self.experiment_id, self.service_name, self.experiment_actual_start_timestamp)

	def time_now(self):
		return datetime.datetime.now().timestamp()

	def add_service(self, service_name):
		if (backend_experiment_db.exists(service_name)):
			return ""
		backend_experiment_db.set(service_name, 
			{'experiment_id':self.experiment_id})

	def init_counters(self):
		self.service_replicas_running 				=	0
		self.jqueuer_worker_count 					=	0

		self.jqueuer_task_added_count				= 	0 
		self.jqueuer_task_running_count				=	0
		self.jqueuer_task_started_count				=	0
		self.jqueuer_task_accomplished_count		=	0
		self.jqueuer_task_accomplished_duration		=	0
		self.jqueuer_task_accomplished_duration_count=	0
		self.jqueuer_task_accomplished_duration_sum	=	0

		self.jqueuer_job_added_count				=	0
		self.jqueuer_job_running_count				=	0
		self.jqueuer_job_started_count				=	0
		self.jqueuer_job_accomplished_count			=	0
		self.jqueuer_job_accomplished_duration		=	0
		self.jqueuer_job_accomplished_duration_count	=	0
		self.jqueuer_job_accomplished_duration_sum	=	0

		self.task_per_job_avg						=	0

		self.jqueuer_job_failed_count				=	0
		self.jqueuer_job_failed_duration				=	0
		self.jqueuer_job_failed_duration_count		=	0
		self.jqueuer_job_failed_duration_sum			=	0
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
		elif (query_var == 'jqueuer_task_accomplished_duration'):
			self.jqueuer_task_accomplished_duration = float(result['value'][1])
		elif (query_var == 'jqueuer_task_accomplished_duration_count'):
			self.jqueuer_task_accomplished_duration_count = int(result['value'][1])
		elif (query_var == 'jqueuer_task_accomplished_duration_sum'):
			self.jqueuer_task_accomplished_duration_sum = float(result['value'][1])
		elif (query_var == 'jqueuer_job_running_count'):
			self.jqueuer_job_running_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_started_count'):
			self.jqueuer_job_started_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_count'):
			self.jqueuer_job_accomplished_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_duration'):
			self.jqueuer_job_accomplished_duration = float(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_duration_count'):
			self.jqueuer_job_accomplished_duration_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_accomplished_duration_sum'):
			self.jqueuer_job_accomplished_duration_sum = float(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_count'):
			self.jqueuer_job_failed_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_duration'):
			self.jqueuer_job_failed_duration = float(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_duration_count'):
			self.jqueuer_job_failed_duration_count = int(result['value'][1])
		elif (query_var == 'jqueuer_job_failed_duration_sum'):
			self.jqueuer_job_failed_duration_sum = float(result['value'][1])
		elif (query_var == 'jqueuer_worker_count'):
			if (result['metric']['service_name'] == self.service_name):
				self.jqueuer_worker_count = int(result['value'][1])

	def process_jobs(self):
		if (isinstance(self.experiment['jobs'], list)):
			self.process_job_list()
		else:
			self.process_job_array()
		self.task_per_job_avg = math.ceil(self.jqueuer_task_added_count / self.jqueuer_job_added_count)

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
		for job in self.experiment['jobs']:
			try:
				job_params = job['params'] 
			except Exception as e:
				job['params'] = self.experiment['params'] 
			try:
				job_command = job['command'] 
			except Exception as e:
				job['command'] = self.experiment['command']

			self.add_job(job)

	def process_job_array(self):
		jobs = self.experiment['jobs']
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
			self.add_job(jobs, job_id)

	def add_tasks(self, tasks, job_id):
		for task in tasks:
			self.jqueuer_task_added_count += 1
			monitoring.add_task(self.experiment_id, self.service_name, job_id, task['id'])

	def add_job(self, job, job_id = None):
		if (not job_id):
			job_id = job["id"]

		self.add_tasks(job['tasks'], job_id)

		self.jqueuer_job_added_count += 1 
		monitoring.add_job(self.experiment_id, self.service_name, job_id)

		job_queue_id = "j_" + self.service_name +"_" + str(int(round(time.time() * 1000))) + "_" + str(random.randrange(100, 999))

		chain = subtask('job_operations.add', queue = JOB_QUEUE_PREFIX + self.service_name)
		chain.delay(self.experiment_id, job_queue_id, job)

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

	def update_service_replicas_running(self):
		self.service_replicas_running = docker_agent.replicas(self.service_name)
		monitoring.service_replicas_running(self.experiment_id, self.service_name, self.service_replicas_running)

	def calc_replica_count(self):
		self.update_service_replicas_running()
		jobs_queued = self.jqueuer_job_added_count - self.jqueuer_job_accomplished_count

		remaining_time	= self.experiment_deadline_timestamp - self.time_now()

		if (self.jqueuer_task_accomplished_duration == 0):
			self.system_calculated_single_task_duration = self.single_task_duration
		else:
			self.system_calculated_single_task_duration = self.jqueuer_task_accomplished_duration
		monitoring.single_task_duration(self.experiment_id, self.service_name, self.system_calculated_single_task_duration)

		service_replicas_needed = 0
		if (remaining_time > 0):
			service_replicas_needed	= 	(jobs_queued * self.system_calculated_single_task_duration * self.task_per_job_avg) / remaining_time
		else:
			service_replicas_needed	= 	(jobs_queued * self.system_calculated_single_task_duration * self.task_per_job_avg)
		
		service_replicas_needed	= 	math.ceil(service_replicas_needed)

		if (self.jqueuer_job_accomplished_count > 0):
			time_spent = self.time_now() - self.experiment_actual_start_timestamp
			time_needed = time_spent * jobs_queued / self.jqueuer_job_accomplished_count
			if (time_needed > remaining_time):
				service_replicas_needed2 = service_replicas_needed
				if (remaining_time > 0):
					service_replicas_needed2 = math.ceil(time_needed * service_replicas_needed / remaining_time)
				else:
					service_replicas_needed2 = jobs_queued
				if (service_replicas_needed2 > service_replicas_needed):
					service_replicas_needed = service_replicas_needed2

		if (service_replicas_needed > self.service_replicas_running):
			if (service_replicas_needed > self.service_replicas_max):
				service_replicas_needed = self.service_replicas_max
		else:
			if (service_replicas_needed < self.service_replicas_min):
				service_replicas_needed = self.service_replicas_min
		monitoring.service_replicas_needed(self.experiment_id, self.service_name, service_replicas_needed)

		return service_replicas_needed, remaining_time

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
		service_replicas_needed, remaining_time = self.calc_replica_count()
		self.run_service(service_replicas_needed)
		coherence_index = 0
		scale = 'none'
		while self.jqueuer_job_accomplished_count < self.jqueuer_job_added_count:
			monitoring.experiment_running_timestamp(self.experiment_id, self.service_name, time.time())
			service_replicas_needed_new, remaining_time = self.calc_replica_count()
			if (service_replicas_needed_new != service_replicas_needed):
				if (coherence_index == 0):
					service_replicas_needed = service_replicas_needed_new

				if (service_replicas_needed > self.service_replicas_running):
					if (scale == 'up'):
						coherence_index += 1
					else:
						coherence_index = 0
						scale = 'up'
				elif (service_replicas_needed < self.service_replicas_running):
					if (scale == 'down'):
						coherence_index += 1
					else:
						coherence_index = 0
						scale = 'down'
				else:
					coherence_index = 0
					scale = 'none'
			else:
				if (service_replicas_needed > self.service_replicas_running):
					coherence_index += 1
					scale = 'up'
				elif (service_replicas_needed < self.service_replicas_running):
					coherence_index += 1
					scale = 'down'
				else:
					coherence_index = 0
					scale = 'none'

			if ((service_replicas_needed != self.service_replicas_running) and (coherence_index > 3)):
				self.scale(service_replicas_needed)
				coherence_index = 0
				scale = 'none'
			time.sleep(math.ceil(self.single_task_duration /4))
		else:
			monitoring.experiment_actual_end_timestamp(self.experiment_id, self.service_name, time.time())
			self.scale(0)
			self.update_service_replicas_running()
			self.remove()