import signal
import zipimport
import grpc

from concurrent import futures
from google.protobuf import any_pb2
from impulse import extract
from pathlib import Path

importer = zipimport.zipimporter("gen.zip")
extract_service_pb2 = importer.load_module("extract_service_pb2")
extract_service_pb2_grpc = importer.load_module("extract_service_pb2_grpc")


PORT = 50051


class ExtractServicer(extract_service_pb2_grpc.ExtractServiceServicer):
    def ExtractData(self, request, context):
        file_container = extract.process_file(request.file_path)
        schema, target_obj = self._read_proto_schema(request.proto_schema)
        json_result = self._extract_json(
            file_container, schema, target_obj, request.model
        )
        proto_instance = self._unpack_json_to_proto(json_result, request.proto_schema)
        any_instance = self._pack_proto_instance(proto_instance)

        return extract_service_pb2.ExtractResponse(
            proto_instance=any_instance,
            json_result=json_result,
        )

    def _read_proto_schema(self, proto_schema):
        path, target_obj = proto_schema.split(":")
        proto_path = Path(path)
        with proto_path.open("r") as proto_file:
            schema = proto_file.read()
        return schema, target_obj

    def _extract_json(self, file_container, schema, target_obj, model):
        json_result = extract.extract_from_file_container(
            file_container, schema, target_obj, model
        )
        return json_result.strip().removeprefix("```json").removesuffix("```")

    def _unpack_json_to_proto(self, json_result, proto_schema):
        path, target_obj = proto_schema.split(":")
        module = self._import_proto_module(path)
        return extract.unpack_json_to_proto(json_result, target_obj, module)

    def _import_proto_module(self, path):
        proto_path = Path(path)
        module_name = str(proto_path.with_suffix("")).replace("protos/", "") + "_pb2"

        # Import the module directly from the ZIP file
        module = importer.load_module(module_name)

        return module

    def _pack_proto_instance(self, proto_instance):
        any_instance = any_pb2.Any()
        any_instance.Pack(proto_instance)
        return any_instance


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    extract_service_pb2_grpc.add_ExtractServiceServicer_to_server(
        ExtractServicer(), server
    )
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"Started server on {PORT}")

    def handle_shutdown(_signum, _frame):
        print("Shutting down gracefully...")
        server.stop(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    serve()
