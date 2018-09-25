FROM python:3.6-slim

COPY requirements.txt /jqueuer_manager/requirements.txt
COPY experiment.py /jqueuer_manager/experiment.py
COPY job_manager.py /jqueuer_manager/job_manager.py
COPY job_operations.py /jqueuer_manager/job_operations.py
COPY experiment_receiver.py /jqueuer_manager/experiment_receiver.py
COPY jqueuer_manager.py /jqueuer_manager/jqueuer_manager.py
COPY parameters.py /jqueuer_manager/parameters.py
COPY monitoring.py /jqueuer_manager/monitoring.py
COPY index.html /jqueuer_manager/index.html
COPY totosca/ /totosca_src/
COPY jqueuer_default_tosca.yaml /etc/jqueuer/tosca/tosca.yaml
ENV TOSCAFILE /etc/jqueuer/tosca/tosca.yaml
ENV PYTHONPATH "${PYTHONPATH}:/totosca_src/"
WORKDIR /jqueuer_manager/
RUN mkdir log
RUN mkdir data
RUN pip install -r requirements.txt
ENTRYPOINT python3 jqueuer_manager.py
