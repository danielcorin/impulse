.PHONY: install compile protos

install:
	uv pip install -r requirements.txt

compile:
	uv pip compile requirements.in -o requirements.txt

protos:
	mkdir -p gen
	find protos -name "*.proto" -type f -exec protoc --python_out=gen {} +

