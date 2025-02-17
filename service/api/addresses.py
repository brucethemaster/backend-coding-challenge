import logging

from datetime import datetime, timedelta

from flask import abort, jsonify, make_response, request
from webargs.flaskparser import use_args

from sqlalchemy import and_, or_, not_

from marshmallow import Schema, fields

from service.server import app, db
from service.models import AddressSegment
from service.models import Person


class GetAddressQueryArgsSchema(Schema):
    date = fields.Date(required=False, missing=datetime.utcnow().date())


class AddressSchema(Schema):
    class Meta:
        ordered = True

    street_one = fields.Str(required=True, max=128)
    street_two = fields.Str(max=128)
    city = fields.Str(required=True, max=128)
    state = fields.Str(required=True, max=2)
    zip_code = fields.Str(required=True, max=10)

    start_date = fields.Date(required=True)
    end_date = fields.Date(required=False)


@app.route("/api/persons/<uuid:person_id>/address", methods=["GET"])
@use_args(GetAddressQueryArgsSchema(), location="querystring")
def get_address(args, person_id):
    person = Person.query.get(person_id)
    date = request.args.get("date")
    if person is None:
        abort(404, description="person does not exist")
    elif len(person.address_segments) == 0:
        abort(404, description="person does not have an address, please create one")

    elif date is not None:
        address_segment = sorted(person.address_segments, key=lambda x: x.start_date)
        address_segment = person.address_segments

        address_segment = filter(
            lambda address_segment: address_segment.start_date
            <= datetime.strptime(date, "%Y-%m-%d").date(),
            address_segment,
        )
        return jsonify(AddressSchema().dump(next(address_segment, None)))
    address_segment = sorted(person.address_segments, key=lambda x: x.start_date)
    return jsonify(AddressSchema(many=True).dump(address_segment))


@app.route("/api/persons/<uuid:person_id>/address", methods=["PUT"])
@use_args(AddressSchema())
def create_address(payload, person_id):
    person = Person.query.get(person_id)

    duplicate_start_date = AddressSegment.query.filter(
        and_(
            AddressSegment.start_date == payload.get("start_date"),
            AddressSegment.person_id == person_id,
        )
    ).first()

    duplicate_address = AddressSegment.query.filter(
        and_(
            AddressSegment.street_one == payload.get("street_one"),
            AddressSegment.street_two == payload.get("street_two"),
            AddressSegment.person_id == person_id,
        )
    ).first()

    if person is None:
        abort(404, description="person does not exist")
    # If there are no AddressSegment records present for the person, we can go
    # ahead and create with no additional logic.

    elif len(person.address_segments) == 0:
        address_segment = AddressSegment(
            street_one=payload.get("street_one"),
            street_two=payload.get("street_two"),
            city=payload.get("city"),
            state=payload.get("state"),
            zip_code=payload.get("zip_code"),
            start_date=payload.get("start_date"),
            person_id=person_id,
        )

        db.session.add(address_segment)
        db.session.commit()
        db.session.refresh(address_segment)
    elif duplicate_start_date is not None:
        error_message = make_response(
            jsonify(
                error="Address segment already exists with start_date "
                + str(payload.get("start_date"))
            ),
            422,
        )

        abort(error_message)
    elif duplicate_address is not None:
        return jsonify(AddressSchema().dump(duplicate_address))
    else:

        address_segment_old = AddressSegment.query.filter(
            and_(AddressSegment.end_date == None, AddressSegment.person_id == person_id)
        ).first()
        address_segment_old.end_date = payload.get("start_date")

        address_segment = AddressSegment(
            street_one=payload.get("street_one"),
            street_two=payload.get("street_two"),
            city=payload.get("city"),
            state=payload.get("state"),
            zip_code=payload.get("zip_code"),
            start_date=payload.get("start_date"),
            person_id=person_id,
        )
        db.session.add(address_segment)
        db.session.commit()
        db.session.refresh(address_segment)
        # TODO: Implementation
        # If there are one or more existing AddressSegments, create a new AddressSegment
        # that begins on the start_date provided in the API request and continues
        # into the future. If the start_date provided is not greater than most recent
        # address segment start_date, raise an Exception.
        # raise NotImplementedError()

    return jsonify(AddressSchema().dump(address_segment))
