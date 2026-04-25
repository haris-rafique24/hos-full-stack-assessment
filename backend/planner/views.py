from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import TripPlanningError, build_trip_plan


def health_view(_request):
    return JsonResponse(
        {
            "message": "HOS backend is running.",
            "endpoints": {
                "health": "/",
                "plan_trip": "/api/plan-trip/ (POST)",
            },
        }
    )


class PlanTripView(APIView):
    def get(self, _request):
        return Response(
            {
                "message": "Use POST to submit trip inputs.",
                "required_fields": [
                    "current_location",
                    "pickup_location",
                    "dropoff_location",
                    "current_cycle_used",
                ],
            }
        )

    def post(self, request):
        current_location = request.data.get("current_location", "").strip()
        pickup_location = request.data.get("pickup_location", "").strip()
        dropoff_location = request.data.get("dropoff_location", "").strip()
        current_cycle_used = request.data.get("current_cycle_used", 0)

        if not current_location or not pickup_location or not dropoff_location:
            return Response(
                {"error": "Current, pickup, and dropoff locations are all required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            current_cycle_used = float(current_cycle_used)
            result = build_trip_plan(
                current_location=current_location,
                pickup_location=pickup_location,
                dropoff_location=dropoff_location,
                current_cycle_used=current_cycle_used,
            )
            return Response(result)
        except (ValueError, TypeError):
            return Response({"error": "Current cycle used must be a number."}, status=status.HTTP_400_BAD_REQUEST)
        except TripPlanningError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": f"Unexpected server error: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
