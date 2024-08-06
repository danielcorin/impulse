.PHONY: install compile protos serve

install:
	uv pip install -r requirements.txt

compile:
	uv pip compile requirements.in -o requirements.txt

protos:
	find protos -name "*.proto" -type f -exec python -m grpc_tools.protoc -I./protos --python_out=./gen.zip --grpc_python_out=./gen.zip {} +

serve:
	watchmedo auto-restart --pattern="*.py" --recursive -- python -m impulse.server
