# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage work form sync with database."""

from flask import current_app
from inflector import English, Inflector

from reports_api.utils.helpers import find_model_from_table_name


class SyncFormDataService:  # pylint:disable=too-few-public-methods
    """Service to sync form data with models."""

    @classmethod
    def _update_or_create(cls, model_class, data: dict):
        current_app.logger.debug(f"_update_or_create with model {model_class} and data {data}")
        # Get the list of column names for the model
        mapper = model_class.__mapper__
        columns = dict(mapper.columns).keys()
        # set data only if key is in column names and has a valid value
        # To avoid passing empty strings to integer / float fields
        data = {k: v for k, v in data.items() if v and k in columns}
        if 'id' in data and data['id']:
            obj = model_class.find_by_id(data['id'])
            obj = obj.update(data)
        else:
            obj = model_class(**data)
            obj = obj.save()
        return obj

    @classmethod
    def _process_model_data(cls, model_name: str, dataset: dict):
        result = None
        model_class = find_model_from_table_name(model_name)

        if model_class:
            # TODO: Look into bulk insert/update for collection of items in payload
            if isinstance(dataset, dict):
                obj = cls._update_or_create(model_class, dataset)
                result = obj.as_dict()
            elif isinstance(dataset, list):
                result = []
                for data in dataset:
                    obj = cls._update_or_create(model_class, data)
                    result.append(obj.as_dict())
        return result

    @classmethod
    def sync_data(cls, payload: dict):
        """Synchronize data from payload with database."""
        result = {}
        inflector = Inflector(English)

        for model_key, dataset in payload.items():
            if model_key not in result:
                foreign_keys = {}
                model_name = model_key
                if '-' in model_key:
                    *relations_list, model_name = model_key.split('-')
                    for relation in relations_list:
                        if relation not in result:
                            result[relation] = cls._process_model_data(relation, payload[relation])
                        relation_key = inflector.singularize(relation)
                        foreign_keys[f'{relation_key}_id'] = result[relation]['id']
            if isinstance(dataset, dict):
                dataset.update(foreign_keys)
            elif isinstance(dataset, list):
                dataset = [{**x, **foreign_keys} for x in dataset]
            obj = cls._process_model_data(model_name, dataset)
            if obj:
                result[model_key] = obj
        return result
