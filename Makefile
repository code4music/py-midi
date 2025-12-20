APP=app
MAIN=$(APP)/main.py
VENV=.venv
PYTHON=$(VENV)/bin/python

.PHONY: default
default: run

.PHONY: venv
venv:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip

.PHONY: install
install: venv
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: run
run:
	$(PYTHON) -m app.main

.PHONY: run-realtime
run-realtime:
	nice -n -19 $(PYTHON) -m app.main

.PHONY: lint
lint:
	$(PYTHON) -m flake8 $(APP)

.PHONY: clean
clean:
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete

.PHONY: reset
reset: clean
	rm -rf $(VENV)

.PHONY: watch
watch:
	@echo "Watching config.yaml & midi_map.yaml (feito pelo watchdog no próprio app)"

.PHONY: dist
dist:
	tar -czvf sf2-synth.tar.gz $(APP) config.yaml midi_map.yaml requirements.txt Makefile
