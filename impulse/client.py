from pathlib import Path
import zipimport
import grpc
import argparse
from typing import Any

importer = zipimport.zipimporter("gen.zip")
extract_service_pb2 = importer.load_module("extract_service_pb2")
extract_service_pb2_grpc = importer.load_module("extract_service_pb2_grpc")


def run(file_path: str, proto_schema: str, model: str):
    channel = grpc.insecure_channel("localhost:50051")
    stub = extract_service_pb2_grpc.ExtractServiceStub(channel)
    request = create_request(file_path, proto_schema, model)
    response = stub.ExtractData(request)
    process_response(response, proto_schema)


def create_request(file_path: str, proto_schema: str, model: str):
    return extract_service_pb2.ExtractRequest(
        file_path=file_path,
        proto_schema=proto_schema,
        model=model,
    )


def process_response(response: extract_service_pb2.ExtractResponse, proto_schema: str):
    print("JSON Result:")
    print(response.json_result)
    unpacked_proto = unpack_proto_instance(response.proto_instance, proto_schema)
    print(f"Proto instance ({type(unpacked_proto)}):")
    print(unpacked_proto)


def unpack_proto_instance(proto_instance: Any, proto_schema: str) -> Any:
    path, target_obj = proto_schema.split(":")
    module = import_proto_module(path)
    proto_class = getattr(module, target_obj)
    unpacked_proto = proto_class()
    if proto_instance.Unpack(unpacked_proto):
        return unpacked_proto
    else:
        raise ValueError("Failed to unpack proto instance")


def import_proto_module(path: str):
    proto_path = Path(path)
    module_name = str(proto_path.with_suffix("")).replace("protos/", "") + "_pb2"

    # Import the module directly from the ZIP file
    module = importer.load_module(module_name)
    return module


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client for ExtractService")
    parser.add_argument("--file_path", type=str, required=True, help="Path to the file")
    parser.add_argument(
        "--proto_schema", type=str, required=True, help="Proto schema and target object"
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["openai", "anthropic"],
        default="openai",
        help="Model to use for extraction",
    )

    args = parser.parse_args()
    run(args.file_path, args.proto_schema, args.model)
