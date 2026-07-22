import json
import os
import sys
from concurrent import futures
from pathlib import Path

import grpc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import football_prediction_pb2 as pb2  # noqa: E402
import football_prediction_pb2_grpc as pb2_grpc  # noqa: E402

from world_cup_intelligence.inference import PredictionService  # noqa: E402


class FootballPrediction(pb2_grpc.FootballPredictionServicer):
    def __init__(self):
        root = Path(os.getenv("PROJECT_ROOT", HERE.parents[1]))
        self.service = PredictionService(root)

    @staticmethod
    def response(value):
        return pb2.JsonResponse(json=json.dumps(value, default=str))

    def PredictMatch(self, request, context):
        return self.response(
            self.service.predict_match(request.home_team_id, request.away_team_id)
        )

    def PredictMarkets(self, request, context):
        return self.PredictMatch(request, context)

    def GetTeamForm(self, request, context):
        return self.response(
            self.service.team_form(request.team_id, request.matches or 5)
        )

    def SimulateTournament(self, request, context):
        path = self.service.root / ("data/predictions/tournament_probabilities.parquet")
        import pandas as pd

        return self.response(pd.read_parquet(path).to_dict("records"))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pb2_grpc.add_FootballPredictionServicer_to_server(FootballPrediction(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
