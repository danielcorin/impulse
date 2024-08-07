.PHONY: install compile protos serve
venv:
	python -m venv .venv
	. .venv/bin/activate && \
	pip install --upgrade pip && \
	pip install uv

install: venv
	. .venv/bin/activate && \
	uv pip install -r requirements.txt

compile: venv
	. .venv/bin/activate && \
	uv pip compile requirements.in -o requirements.txt

protos:
	find protos -name "*.proto" -type f -exec python -m grpc_tools.protoc -I./protos --python_out=./gen.zip --grpc_python_out=./gen.zip {} +

serve:
	. .venv/bin/activate && \
	watchmedo auto-restart --pattern="*.py" --recursive -- python -m impulse.server
