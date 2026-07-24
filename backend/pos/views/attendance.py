"""CiXiS staff tracker API: roster, shift attendance, and per-person tab.

Brand-gated to CiXiS in the UI. Consistent with the rest of the POS, the reveal
password is a UI affordance handled by the frontend gate; these routes are not
individually re-verified (the app runs on 127.0.0.1 for a single operator).
"""
from datetime import date

from rest_framework import status, viewsets
from rest_framework.response import Response

from ..models import Employee, ShiftAttendance, StaffConsumption
from ..serializers import (
    EmployeeSerializer,
    ShiftAttendanceSerializer,
    StaffConsumptionSerializer,
)


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class EmployeeViewSet(viewsets.ModelViewSet):
    """Staff roster CRUD. Destroy is a soft delete so history keeps its names."""

    serializer_class = EmployeeSerializer
    queryset = Employee.objects.filter(is_active=True)

    def perform_create(self, serializer):
        if serializer.validated_data.get("sort_order") in (None, 0):
            last = (
                Employee.objects.filter(is_active=True)
                .order_by("-sort_order")
                .values_list("sort_order", flat=True)
                .first()
            )
            serializer.save(sort_order=(last or 0) + 1)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        employee.is_active = False
        employee.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShiftAttendanceViewSet(viewsets.ModelViewSet):
    """Attendance rows, filterable by ?date= and ?shift= to prefill the entry grid.

    ``create`` upserts on (employee, business_date, shift) so re-saving a row the
    supervisor already entered just updates its times instead of 409-ing on the
    unique constraint.
    """

    serializer_class = ShiftAttendanceSerializer
    queryset = ShiftAttendance.objects.select_related("employee").all()

    def get_queryset(self):
        qs = super().get_queryset()
        business_date = _parse_date(self.request.query_params.get("date"))
        if business_date is not None:
            qs = qs.filter(business_date=business_date)
        shift = self.request.query_params.get("shift")
        if shift:
            qs = qs.filter(shift=shift)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj, created = ShiftAttendance.objects.update_or_create(
            employee=data["employee"],
            business_date=data["business_date"],
            shift=data["shift"],
            defaults={
                "check_in": data["check_in"],
                "check_out": data["check_out"],
                "is_full_day": data.get("is_full_day", False),
            },
        )
        out = self.get_serializer(obj)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out.data, status=code)


class StaffConsumptionViewSet(viewsets.ModelViewSet):
    """Per-person bill entries, filterable by employee, date range, and shift."""

    serializer_class = StaffConsumptionSerializer
    queryset = StaffConsumption.objects.select_related("employee").all()

    def get_queryset(self):
        qs = super().get_queryset()
        employee = self.request.query_params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        exact = _parse_date(self.request.query_params.get("date"))
        if exact is not None:
            qs = qs.filter(business_date=exact)
        shift = self.request.query_params.get("shift")
        if shift:
            qs = qs.filter(shift=shift)
        from_date = _parse_date(self.request.query_params.get("from"))
        if from_date is not None:
            qs = qs.filter(business_date__gte=from_date)
        to_date = _parse_date(self.request.query_params.get("to"))
        if to_date is not None:
            qs = qs.filter(business_date__lte=to_date)
        return qs
