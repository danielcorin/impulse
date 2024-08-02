.PHONY: install compile protos serve

install:
	uv pip install -r requirements.txt

compile:
	uv pip compile requirements.in -o requirements.txt

protos:
	mkdir -p gen/protos
	touch gen/__init__.py
	touch gen/protos/__init__.py
	find protos -name "*.proto" -type f -exec python -m grpc_tools.protoc -I./protos --python_out=./gen/protos --grpc_python_out=./gen/protos {} +
	sed -i '' 's/import extract_service_pb2 as extract__service__pb2/from gen.protos import extract_service_pb2 as extract__service__pb2/' gen/protos/extract_service_pb2_grpc.py

serve:
	watchmedo auto-restart --pattern="*.py" --recursive -- python -m impulse.server
