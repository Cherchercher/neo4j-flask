from collections import defaultdict
from . import config
import binascii
import hashlib
import os
import re
import sys
import uuid
from functools import wraps

from flask import Flask, g, request, send_from_directory, abort, request_started
from flask_cors import CORS
from flask_restful import Resource, reqparse
from flask_restful_swagger_2 import Api, swagger, Schema

from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import Neo4jError

from flask_py2neo import Py2Neo
db = Py2Neo()

# api = Api(app, title='Zocdoc API for CC', api_version='0.0.10')

# driver = GraphDatabase.driver(config.DATABASE_URL,  encrypted=False,  auth=basic_auth(
#     config.DATABASE_USERNAME, str(config.DATABASE_PASSWORD)))


# def create_app():
#     """
#     Create a Flask application using the app factory pattern.

#     :param settings_override: Override settings
#     :return: Flask app
#     """
#     app = Flask(__name__)
#     app.config['SECRET_KEY'] = 'super secret guy'
#     api = Api(app, title='Zocdoc API for CC', api_version='0.0.10')
#     CORS(app)


#     driver = GraphDatabase.driver(config.DATABASE_URL, auth=basic_auth(
#         config.DATABASE_USERNAME, str(config.DATABASE_PASSWORD)))


def get_db():
    return db
    # if not hasattr(g, 'neo4j_db'):
    #     g.neo4j_db = driver.session()
    # return g.neo4j_db


class InsuranceModel(Schema):
    type = 'object'
    properties = {
        'name': {
            'type': 'string',
        }
    }


class SpecialtyModel(Schema):
    type = 'object'
    properties = {
        'name': {
            'type': 'string',
        }
    }


class LanguageModel(Schema):
    type = 'object'
    properties = {
        'name':  {
            'type': 'string',
        }
    }


class DoctorModel(Schema):
    type = 'object'
    properties = {
        'name': {
            'type': 'string',
        },
        'bedside_manner': {
            'type': 'float',
        },
        'wait_time': {
            'type': 'float',
        },
        'gender': {
            'type': 'string',
        },
        'image': {
            'type': 'string',
        },
        'specialties': {
            'type': 'list',
        },
        'education': {
            'type': 'string',
        },
        'street_address': {
            'type': 'string',
        },
        'insurance': {
            'type': 'list',
        },
        'zoc_award': {
            'type': 'list',
        },
        'languages': {
            'type': 'list',
        },
        'lat': {
            'type': 'float',
        },
        'lng': {
            'type': 'float',
        }
    }


def serialize_doctor(doctor):
    properties = doctor['root']
    properties['zid'] = doctor['id']
    # if hasattr(doctor, 'relations'):
    for relation in doctor['relations']:
        if relation[0] in properties:
            properties[relation[0]].append(relation[1])
        else:
            properties[relation[0]] = [relation[1]]
    return properties
    # else:
    #     return doctor['root']


def serialize_doctor_address(doctor, a, l):
    dictR = defaultdict(dict)
    for k, v in l.items():
        dictR[doctor['name']][a['labels']] = v
    return dictR


def serialize_insurance(insurance):
    return {
        'name': insurance['name']
    }


def serialize_specialty(specialty):
    return {
        'name': specialty['name']
    }


def serialize_language(language):
    return {
        'name': language['name']
    }


class DoctorList(Resource):
    @ swagger.doc({
        'tags': ['doctors'],
        'summary': 'find doctors satisfying constraints',
        'description': 'Returns count and list of doctors with applied filters and sorting',
        'parameters': [
            {
                'name': 'lat',
                'description': 'geo location lat',
                'in': 'query',
                'type': 'string'
            },
            {
                'name': 'lng',
                'description': 'geo location lng',
                'in': 'path',
                'type': 'string'
            },
            {
                'name': 'within',
                'description': 'search within radius in meters, default 80000',
                'in': 'query',
                'type': 'number'
            },
            {
                'name': 'skip',
                'description': 'offsets doctors to return. default 0',
                'in': 'query',
                'type': 'integer'
            },
            {
                'name': 'limit',
                'description': 'number of doctors to return. default 0',
                'in': 'query',
                'type': 'integer'
            },
            {
                'name': 'language',
                'description': 'filter by language',
                'in': 'query',
                'type': 'string'
            },
            {
                'name': 'specialty',
                'description': 'filter by specialty',
                'in': 'query',
                'type': 'string'
            },
            {
                'name': 'sort_by',
                'description': 'sort doctors by. Options: overall_rating, bedside_manner, wait_time, distance. Default value: overall_rating',
                'in': 'query',
                'type': 'string'
            },
        ],
        'responses': {
            '200': {
                'description': 'A list of doctors sort by overall ratings',
                'schema': {
                    'type': 'array',
                    'items': DoctorModel,
                }
            }
        }
    })
    def get(self):
        def get_doctors(tx, criteriaStr, sortStr, language, insurance, specialty, lat, lng, skip=0, limit=50):
            if criteriaStr != "":
                return list(tx.run(
                    """
                    MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
                    """ +
                    criteriaStr +
                    """
                    WITH doctor, a
                    """ +
                    sortStr +
                    """
                    MATCH (doctor)-[r]-(l)
                    with doctor, a, [type(r), l] as relation, ID(doctor) as id

                    return { root: doctor, relations: collect(relation), id: id }
                    Skip toInteger($skip) LIMIT toInteger($limit)

                    """, {'limit': limit, 'language': language, 'insurance': insurance, 'specialty': specialty, 'skip': skip, 'lat': lat, 'lng': lng}
                ).data())

            else:
                return list(tx.run(
                    """
                    MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
                    WITH doctor, a
                    MATCH (doctor)-[r]-(l)
                    with doctor, a, [type(r), l] as relation, ID(doctor) as id
                    """ +
                    sortStr +
                    """
                    return { root: doctor, relations: collect(relation), id: id }
                    Skip toInteger($skip) LIMIT toInteger($limit)
                    """, {'limit': limit, 'skip': skip}
                ).data())

        def get_doctors_count(tx, criteriaStr, language, insurance, specialty, lat, lng):
            if criteriaStr == "":
                return list(tx.run(
                    '''
                    MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
                    RETURN COUNT(DISTINCT(doctor)) AS count
                    '''
                ).data())
            else:
                return list(tx.run(
                    '''
                    MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
                    with doctor, a
                    MATCH (doctor)-[r]-(l)
                    ''' +
                    criteriaStr +
                    '''
                    RETURN COUNT(DISTINCT(doctor)) AS count
                    ''', {'language': language, 'insurance': insurance, 'specialty': specialty, 'lat': lat, 'lng': lng}
                ).data())

        skip = request.args.get('skip')
        limit = request.args.get('limit')
        insurance = request.args.get('insurance')
        language = request.args.get('language')
        specialty = request.args.get('specialty')
        sort_by = request.args.get('sort_by')
        within = request.args.get('meter')
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        meter = 80000
        if within:
            meter = within
        sortStr = ""
        if sort_by == 'overall_rating':
            sortStr = "ORDER BY coalesce(doctor.overall_rating, 0) DESC"
        if sort_by == 'bedside_manner':
            sortStr = "ORDER BY coalesce(doctor.bedside_manner, 0) DESC"
        if sort_by == 'wait_time':
            sortStr = "ORDER BY coalesce(doctor.wait_time, 0) DESC"
        if sort_by == "distance":
            sortStr = "ORDER BY distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: toFloat($lat), longitude:  toFloat($lng)}))"
        criteria = []
        criteriaValue = []
        criteriaStr = ""
        if specialty:
            criteria.append(" (doctor)-[:SPECIALIZE_IN]->(specialty)")
            criteriaValue.append(
                "toLower(specialty.name) = toLower($specialty)")

        if insurance:
            criteria.append(" (doctor)-[:SUPPORTS_INSUR]->(insurance)")
            criteriaValue.append(
                "toLower(insurance.name) = toLower($insurance)")
        if language:
            criteria.append(" (doctor)-[:SPEAKS]->(language)")
            criteriaValue.append(
                "toLower(language.name) = toLower($language)")

        if len(criteria) == 1:
            criteriaStr += ", "
            criteriaStr += criteria[0]
            criteriaStr += " WHERE "
            criteriaStr += criteriaValue[0]
            criteriaStr += " "
        if len(criteria) > 1:
            criteriaStr += ", "
            criteriaStr += (",").join(criteria)
            criteriaStr += ' WHERE '
            criteriaStr += (" AND ").join(criteriaValue)
        if lat and lng:
            if len(criteria) > 0:
                criteriaStr += (" AND ")
                criteriaStr += "distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: toFloat($lat), longitude:  toFloat($lng)})) <= "
                criteriaStr += str(meter)
            else:
                criteriaStr += " WHERE "
                criteriaStr += "distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: toFloat($lat), longitude:  toFloat($lng)})) <= "
                criteriaStr += str(meter)

        db = get_db()
        if skip and limit:
            result = get_doctors(db.graph, criteriaStr, sortStr,
                                 language, insurance, specialty, lat, lng, skip, limit)
        else:
            result = get_doctors(db.graph, criteriaStr, sortStr,
                                 language, insurance, specialty, lat, lng)
        countResult = get_doctors_count(
            db.graph, criteriaStr, language, insurance, specialty, lat, lng)
        count = 0
        if len(countResult) != 0:
            count = countResult[0]['count']

        return{'count': count, 'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


class InsuranceList(Resource):
    @ swagger.doc({
        'tags': ['insurance'],
        'summary': 'Find all insurance providers',
        'description': 'Returns a list of insurance providers',
        'responses': {
            '200': {
                'description': 'A list of insurance providers',
                'schema': {
                    'type': 'array',
                    'items': InsuranceModel,
                }
            }
        }
    })
    def get(self):
        def get_insurance(tx):
            return list(tx.run(
                '''
                MATCH (insurance:Insurance) RETURN insurance
                '''
            ).data())
        db = get_db()
        result = get_insurance(db.graph)
        return [serialize_insurance(record['insurance']) for record in result]


class LanguageList(Resource):
    @ swagger.doc({
        'tags': ['language'],
        'summary': 'Find all languages',
        'description': 'Returns a list of languages',
        'responses': {
            '200': {
                'description': 'A list of languages',
                'schema': {
                    'type': 'array',
                    'items': LanguageModel,
                }
            }
        }
    })
    def get(self):
        def get_language(tx):
            return list(tx.run(
                '''
                MATCH (language:Language) RETURN language
                '''
            ).data())
        db = get_db()
        result = get_language(db.graph)
        return [serialize_language(record['language']) for record in result]


# class DoctorListBySpecialty(Resource):
#     @ swagger.doc({
#         'tags': ['doctors'],
#         'summary': 'Find movie by specialty',
#         'description': 'Returns a list of doctors by specialty',
#         'parameters': [
#             {
#                 'name': 'specialty_name',
#                 'description': 'specialty name',
#                 'in': 'path',
#                 'type': 'integer',
#                 'required': 'true'
#             }
#         ],
#         'responses': {
#             '200': {
#                 'description': 'A list of doctors with the specified specialty',
#                 'schema': {
#                     'type': 'array',
#                     'items': DoctorModel,
#                 }
#             }
#         }
#     })
#     def get(self, specialty_name):
#         def get_doctors_by_specialty(tx, specialty_name, skip=0, limit=50):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:SPECIALIZE_IN]->(specialty),
#                 (doctor)-[:SPEAKS]-> (language),
#                 (doctor)-[:SUPPORTS_INSUR]-> (insurance)
#                 WHERE toLower(specialty.name) = toLower($specialty_name)
#                 AND toLower(language.name) = toLower($language_name)
#                 AND toLower(insurance.name) = toLower($insurance_name)
#                 WITH doctor
#                 MATCH (doctor)-[r]-(l)
#                 with doctor, [type(r),l] as relation, ID(doctor) as id
#                 RETURN { root: doctor, relations: collect(relation), id: id }
#                 Skip toInteger($skip) LIMIT toInteger($limit )
#                 ''', {'specialty_name': specialty_name, 'skip': skip, 'limit': limit, 'language_name': 'spanish', 'insurance_name': 'cigna'}
#             ).data())

#         def get_doctors_by_specialty_count(tx, specialty_name):
#             return list(db.graph.run('''
#                 MATCH (doctor:Doctor)-[:SPECIALIZE_IN]->(specialty)
#                 WHERE toLower(specialty.name) = toLower($specialty_name)
#                 RETURN COUNT(DISTINCT(doctor)) AS count
#                 ''', {'specialty_name': specialty_name}).data())

#         skip = request.args.get('skip')
#         limit = request.args.get('limit')
#         db = get_db()
#         if skip and limit:
#             result = get_doctors_by_specialty(
#                 db.graph, specialty_name, skip, limit)
#         else:
#             result = get_doctors_by_specialty(db.graph, specialty_name)
#         countResult = get_doctors_by_specialty_count(db.graph, specialty_name)
#         count = 0
#         if len(countResult) != 0:
#             count = countResult[0]['count']
#         return{'count': count, 'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


# class DoctorListByLanguage(Resource):
#     @ swagger.doc({
#         'tags': ['doctors'],
#         'summary': 'Find doctors by language',
#         'description': 'Returns a list of doctors who speak the specified language',
#         'parameters': [
#             {
#                 'name': 'language_name',
#                 'description': 'language name',
#                 'in': 'path',
#                 'type': 'string',
#                 'required': 'true'
#             },
#         ],
#         'responses': {
#             '200': {
#                 'description': 'A list of doctors who speak the specified language',
#                 'schema': {
#                     'type': 'array',
#                     'items': DoctorModel,
#                 }
#             }
#         }
#     })
#     def get(self, language_name):
#         def get_doctors_by_language(tx, language_name, skip=10, limit=50):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:SPEAKS]->(language)
#                 WHERE toLower(language.name) = toLower($language_name)
#                 WITH doctor
#                 MATCH (doctor)-[r]-(l)
#                 with doctor, [type(r),l] as relation, ID(doctor) as id
#                 RETURN { root: doctor, relations: collect(relation), id: id }
#                 Skip toInteger($skip) LIMIT toInteger($limit )
#                 ''', {'language_name': language_name, 'language_name': language_name, 'skip': skip, 'limit': limit}
#             ).data())

#         def get_doctors_by_language_count(tx, language_name):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:SPEAKS]->(language)
#                 WHERE toLower(language.name) = toLower($language_name)
#                 RETURN COUNT(DISTINCT(doctor)) AS count
#                 ''', {'language_name': language_name, 'language_name': language_name}
#             ).data())

#         skip = request.args.get('skip')
#         limit = request.args.get('limit')
#         db = get_db()
#         if skip and limit:
#             result = get_doctors_by_language(
#                 db.graph, language_namee, skip, limit)
#         else:
#             result = get_doctors_by_language(db.graph, language_name)
#         countResult = get_doctors_by_language_count(db.graph, language_name)
#         count = 0
#         if len(countResult) != 0:
#             count = countResult[0]['count']
#         return {'count': count, 'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


class DoctorListByID(Resource):
    @ swagger.doc({
        'tags': ['doctors'],
        'summary': 'Find doctors by id',
        'description': 'Returns the doctor with specified id',
        'parameters': [
            {
                'name': 'language_name',
                'description': 'language name',
                'in': 'path',
                'type': 'string',
                'required': 'true'
            },
        ],
        'responses': {
            '200': {
                'description': 'A doctor with the specified id',
                'schema': {
                    'type': 'array',
                    'items': DoctorModel,
                }
            }
        }
    })
    def get(self, doctor_id):
        def get_doctors_by_id(tx, id):
            return list(tx.run(
                '''
                MATCH (doctor:Doctor)
                WHERE ID(doctor) = toInteger($id)
                WITH doctor
                MATCH (doctor)-[r]-(l)
                with doctor, [type(r),l] as relation, ID(doctor) as id

                RETURN { root: doctor, relations: collect(relation), id: id }
                ''', {'id': id}
            ).data())

        db = get_db()
        result = get_doctors_by_id(db.graph, doctor_id)
        return {'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


class SpecialtyList(Resource):
    @ swagger.doc({
        'tags': ['specialty'],
        'summary': 'Find all specialties',
        'description': 'Returns a list of specialties',
        'responses': {
            '200': {
                'description': 'A list of specialties',
                'schema': {
                    'type': 'array',
                    'items': SpecialtyModel,
                }
            }
        }
    })
    def get(self):
        def get_specialty(tx):
            return list(tx.run(
                '''
                MATCH (specialty: Specialty) RETURN specialty
                '''
            ).data())
        db = get_db()
        result = get_specialty(db.graph)
        return [serialize_specialty(record['specialty']) for record in result]


# class NearestDoctor(Resource):
#     @ swagger.doc({
#         'tags': ['doctors'],
#         'summary': 'Find doctors near a geo location',
#         'description': 'Returns a list of doctors near the geo location',
#         'parameters': [
#             {
#                 'name': 'lat',
#                 'description': 'geo location lat',
#                 'in': 'query',
#                 'type': 'string',
#                 'required': 'false'
#             },
#             {
#                 'name': 'lng',
#                 'description': 'geo location lng',
#                 'in': 'path',
#                 'type': 'string',
#                 'required': 'false'
#             },
#             {
#                 'name': 'within',
#                 'description': 'search within radius in meters, default 80000',
#                 'in': 'query',
#                 'type': 'float',
#                 'required': 'false'
#             },
#             {
#                 'name': 'skip',
#                 'description': 'offsets doctors to return. default 0',
#                 'in': 'query',
#                 'type': 'int',
#                 'required': 'false'
#             },
#             {
#                 'name': 'limit',
#                 'description': 'number of doctors to return. default 0',
#                 'in': 'query',
#                 'type': 'int',
#                 'required': 'false'
#             },
#             {
#                 'name': 'language',
#                 'description': 'filter by language',
#                 'in': 'query',
#                 'type': 'string',
#                 'required': 'false'
#             },
#             {
#                 'name': 'specialty',
#                 'description': 'filter by specialty',
#                 'in': 'query',
#                 'type': 'string',
#                 'required': 'false'
#             },
#             {
#                 'name': 'specialty',
#                 'description': 'filter by insurance',
#                 'in': 'query',
#                 'type': 'string',
#                 'required': 'false'
#             },
#         ],
#         'responses': {
#             '200': {
#                 'description': 'A list of doctors near the geo location',
#                 'schema': {
#                     'type': 'array',
#                     'items': DoctorModel,
#                 }
#             }
#         }
#     })
#     def get(self, lat, lng):
#         def get_doctors_by_location(tx, lat, lng, criteriaStr, language, insurance, specialty, skip=0, limit=50):
#             if criteriaStr != "":
#                 return list(tx.run(
#                     """
#                     MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
#                     """ +
#                     criteriaStr +

#                     """
#                     with doctor, a
#                     MATCH (doctor)-[r2]-(l)
#                     with doctor, a, [type(r2), l] as relation, ID(doctor) as id
#                     ORDER BY distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: $lat, longitude:  $lng}))
#                     return { root: doctor, relations: collect(relation), id: id }
#                     Skip toInteger($skip) LIMIT toInteger($limit)
#                     """, {'lat': lat, 'lng': lng, 'limit': limit, 'language': language, 'insurance': insurance, 'specialty': specialty, 'skip': skip}
#                 ).data())
#             else:
#                 return list(tx.run(
#                     '''
#                     MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
#                     with doctor, a
#                     MATCH (doctor)-[r2]-(l)
#                     with doctor, a, [type(r2), l] as relation, ID(doctor) as id
#                     ORDER BY distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: $lat, longitude:  $lng}))
#                     return { root: doctor, relations: collect(relation), id: id }
#                     Skip toInteger($skip) LIMIT toInteger($limit)
#                     ''', {'lat': lat, 'lng': lng, 'limit': limit, 'skip': skip}
#                 ).data())

#         def get_doctors_by_location_count(tx, lat, lng, criteriaStr, language, insurance, specialty):
#             if criteriaStr == "":
#                 return list(tx.run(
#                     '''
#                     MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
#                     RETURN COUNT(DISTINCT(doctor)) AS count
#                     ''', {'lat': lat, 'lng': lng}
#                 ).data())
#             else:
#                 return list(tx.run(
#                     '''
#                     MATCH (doctor:Doctor)-[r1:HAS_ADDRESS]-(a:Address)
#                     ''' +
#                     criteriaStr +
#                     '''
#                     RETURN COUNT(DISTINCT(doctor)) AS count
#                     ''', {'lat': lat, 'lng': lng, 'language': language, 'insurance': insurance, 'specialty': specialty}
#                 ).data())

#         skip = request.args.get('skip')
#         limit = request.args.get('limit')
#         insurance = request.args.get('insurance')
#         language = request.args.get('language')
#         specialty = request.args.get('specialty')
#         within = request.args.get('meter')
#         meter = 80000
#         if within:
#             meter = within
#         criteria = []
#         criteriaValue = []
#         criteriaStr = ""
#         if specialty:
#             criteria.append(" (doctor)-[:SPECIALIZE_IN]->(specialty)")
#             criteriaValue.append(
#                 "toLower(specialty.name) = toLower($specialty)")
#         if insurance:
#             criteria.append(" (doctor)-[:SUPPORTS_INSUR]->(insurance)")
#             criteriaValue.append(
#                 "toLower(insurance.name) = toLower($insurance)")
#         if language:
#             criteria.append(" (doctor)-[:SPEAKS]->(language)")
#             criteriaValue.append(
#                 "toLower(language.name) = toLower($language)")
#         if len(criteria) == 1:
#             criteriaStr += ", "
#             criteriaStr += criteria[0]
#             criteriaStr += " WHERE "
#             criteriaStr += criteriaValue[0]
#             criteriaStr += " "
#         if len(criteria) > 1:
#             criteriaStr += ", "
#             criteriaStr += (",").join(criteria)
#             criteriaStr += ' WHERE '
#             criteriaStr += (" AND ").join(criteriaValue)
#         if len(criteria) > 0:
#             criteriaStr += (" AND ")
#             criteriaStr += "distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: $lat, longitude:  $lng})) <= "
#             criteriaStr += str(meter)
#         else:
#             criteriaStr += " WHERE "
#             criteriaStr += "distance(point({latitude: toFloat(a.lat), longitude:toFloat(a.lng)}), point({latitude: $lat, longitude:  $lng})) <= "
#             criteriaStr += str(meter)

#         db = get_db()
#         if skip and limit:
#             result = get_doctors_by_location(
#                 db.graph,  float(lat), float(lng), criteriaStr, language, insurance, specialty, skip, limit)
#         else:
#             result = get_doctors_by_location(
#                 db.graph,  float(lat), float(lng), criteriaStr, language, insurance, specialty)
#         countResult = get_doctors_by_location_count(
#             db.graph,  float(lat), float(lng), criteriaStr, language, insurance, specialty)
#         count = 0
#         if len(countResult) != 0:
#             count = countResult[0]['count']
#         return {'count': count, 'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


# class DoctorListByInsurance(Resource):
#     @ swagger.doc({
#         'tags': ['doctors'],
#         'summary': 'Find doctors by insurance',
#         'description': 'Returns a list of doctors who accepts the insurance provider',
#         'parameters': [
#             {
#                 'name': 'insurance_name',
#                 'description': 'insurance name',
#                 'in': 'path',
#                 'type': 'string',
#                 'required': 'true'
#             },
#         ],
#         'responses': {
#             '200': {
#                 'description': 'A list of doctors who accepts the insurance provider',
#                 'schema': {
#                     'type': 'array',
#                     'items': DoctorModel,
#                 }
#             }
#         }
#     })
#     def get(self, insurance_name):
#         def get_doctors_by_insurance(tx, insurance_name, skip=0, limit=50):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:SUPPORTS_INSUR]->(insurance)
#                 WHERE insurance.name = $insurance_name
#                 WITH doctor
#                 MATCH (doctor)-[r]-(l)
#                 with doctor, [type(r),l] as relation, ID(doctor) as id
#                 RETURN { root: doctor, relations: collect(relation), id: id }
#                 Skip toInteger($skip) LIMIT toInteger($limit )
#                 ''', {'insurance_name': insurance_name, 'limit': limit, 'skip': skip}
#             ).data())

#         def get_doctors_by_insurance_count(tx, insurance_name):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:SUPPORTS_INSUR]->(insurance)
#                 WHERE insurance.name = $insurance_name
#                 RETURN COUNT(DISTINCT(doctor)) AS count
#                 ''', {'insurance_name': insurance_name}
#             ).data())
#         db = get_db()
#         skip = request.args.get('skip')
#         limit = request.args.get('limit')
#         if skip and limit:
#             result = get_doctors_by_insurance(
#                 db.graph, insurance_name, skip, limit)
#         else:
#             result = get_doctors_by_insurance(db.graph, insurance_name)
#         countResult = get_doctors_by_insurance_count(db.graph, insurance_name)
#         count = 0
#         if len(countResult) != 0:
#             count = countResult[0]['count']
#         return{'count': count, 'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


# class DoctorListByEducation(Resource):
#     @ swagger.doc({
#         'tags': ['doctors'],
#         'summary': 'Find doctors by education',
#         'description': 'Returns a list of doctors who completes an education',
#         'parameters': [
#             {
#                 'name': 'program_name',
#                 'description': 'program name',
#                 'in': 'path',
#                 'type': 'string',
#                 'required': 'true'
#             },
#         ],
#         'responses': {
#             '200': {
#                 'description': 'A list of doctors who completes an education',
#                 'schema': {
#                     'type': 'array',
#                     'items': DoctorModel,
#                 }
#             }
#         }
#     })
#     def get(self, program_name):
#         def get_doctors_by_program(tx, program_name, skip=0,  limit=50):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:HAS_EDUCATION]->(edu)
#                 WHERE toLower(edu.name) = toLower($program_name)
#                 WITH doctor
#                 MATCH (doctor)-[r]-(l)
#                 with doctor, [type(r),l] as relation, ID(doctor) as id
#                 RETURN { root: doctor, relations: collect(relation), id: id }
#                 Skip toInteger($skip) LIMIT toInteger($limit )
#                 ''', {'program_name': program_name, 'limit': limit, 'skip': skip}
#             ).data())

#         def get_doctors_by_program_count(tx, program_name):
#             return list(tx.run(
#                 '''
#                 MATCH (doctor:Doctor)-[:HAS_EDUCATION]->(edu)
#                 WHERE toLower(edu.name) = toLower($program_name)
#                 RETURN COUNT(DISTINCT(doctor)) AS count
#                 ''', {'program_name': program_name}
#             ).data())
#         db = get_db()
#         skip = request.args.get('skip')
#         limit = request.args.get('limit')
#         if skip and limit:
#             result = get_doctors_by_program(
#                 db.graph, program_name, skip, limit)
#         else:
#             result = get_doctors_by_program(db.graph, program_name)

#         countResult = get_doctors_by_program_count(db.graph, program_name)
#         count = 0
#         if len(countResult) != 0:
#             count = countResult[0]['count']
#         return{'count': count, 'result': [serialize_doctor(record['{ root: doctor, relations: collect(relation), id: id }']) for record in result]}


class ApiDocs(Resource):
    def get(self, path=None):
        if not path:
            path = 'index.html'
        return send_from_directory('swaggerui', path)


TEST_DB_URI = 'localhost'
TEST_DB_HTTP = 11004
TEST_DB_BOLT = 11005


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'super secret guy'
    CORS(app,  resources={r"/api/*": {"origins": "*"},
                          r"/docs": {"origins": "*"}})
    # app.config.update({
    #     'PY2NEO_HOST': 'db'
    # })

    # config = {
    #     'TESTING': True,
    #     # 'PY2NEO_BOLT': None,  # without this, creating a relationship off the OGM threw an error
    #     'PY2NEO_HOST': TEST_DB_URI,
    #     'PY2NEO_HTTP_PORT': TEST_DB_HTTP,
    #     'PY2NEO_BOLT_PORT': TEST_DB_BOLT
    # }

    # app.config.update(config or {})
    # app.config.update({
    #     'PY2NEO_BOLT_PORT': '11005'
    # })

    db.init_app(app)

    api = Api(app, title='Zocdoc API for CC', api_version='0.0.10')
    api.add_resource(ApiDocs, '/docs', '/docs/<path:path>')
    api.add_resource(DoctorList, '/api/v0/doctors')
    # api.add_resource(DoctorListBySpecialty,
    #                  '/api/v0/doctors/specialty/<string:specialty_name>')
    # api.add_resource(DoctorListByInsurance,
    #                  '/api/v0/doctors/insurance/<string:insurance_name>')
    # api.add_resource(DoctorListByLanguage,
    #                  '/api/v0/doctors/language/<string:language_name>')
    api.add_resource(DoctorListByID,
                     '/api/v0/doctors/id/<string:doctor_id>')
    # api.add_resource(NearestDoctor,
    #                  '/api/v0/nearestdoctors/<string:lat>/<string:lng>')
    api.add_resource(InsuranceList, '/api/v0/insurance')
    api.add_resource(LanguageList, '/api/v0/languages')
    api.add_resource(SpecialtyList, '/api/v0/specialties')
    # api.add_resource(DoctorListByEducation,
    #                  '/api/v0/doctors/education/<string:program_name>')

    # more setup here

    @ app.route('/')
    def index():
        """
        Render a Hello World response.

        :return: Flask response
        """
        return 'Hello World!'

    # @app.teardown_appcontext
    # def close_db(error):
    #     if hasattr(g, 'neo4j_db'):
    #         g.neo4j_db.close()
    return app


app = create_app()

if __name__ == "__main__":
    app.run()
