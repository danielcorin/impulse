from pathlib import Path
import grpc
from concurrent import futures
from gen.protos import extract_service_pb2
from gen.protos import extract_service_pb2_grpc
from impulse import extract
from google.protobuf import any_pb2
import importlib


class ExtractServicer(extract_service_pb2_grpc.ExtractServiceServicer):
    def ExtractData(self, request, context):
        file_container = extract.process_file(request.file_path)
        schema = self._read_proto_schema(request.proto_schema)
        json_result = self._extract_json(file_container, schema, request.model)
        proto_instance = self._unpack_json_to_proto(json_result, request.proto_schema)
        any_instance = self._pack_proto_instance(proto_instance)

        return extract_service_pb2.ExtractResponse(
            json_result=json_result, proto_instance=any_instance
        )

    def _read_proto_schema(self, proto_schema):
        path, _ = proto_schema.split(":")
        proto_path = Path(path)
        with proto_path.open("r") as proto_file:
            return proto_file.read()

    def _extract_json(self, file_container, schema, model):
        json_result = extract.extract_from_file_container(file_container, schema, model)
        return json_result.replace("```json", "").replace("```", "")

    def _unpack_json_to_proto(self, json_result, proto_schema):
        path, target_obj = proto_schema.split(":")
        module = self._import_proto_module(path)
        return extract.unpack_json_to_proto(json_result, target_obj, module)

    def _import_proto_module(self, path):
        proto_path = Path(path)
        module_name = proto_path.stem + "_pb2"
        gen_path = Path("gen") / proto_path.relative_to(proto_path.anchor)
        gen_path = gen_path.with_name(module_name + ".py")
        spec = importlib.util.spec_from_file_location(module_name, str(gen_path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _pack_proto_instance(self, proto_instance):
        any_instance = any_pb2.Any()
        any_instance.Pack(proto_instance)
        return any_instance


def serve():
    print("starting server")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    extract_service_pb2_grpc.add_ExtractServiceServicer_to_server(
        ExtractServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
