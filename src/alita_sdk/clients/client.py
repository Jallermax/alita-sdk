import logging
import requests

from os import environ
from typing import Dict, List, Any, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
)

from langchain_core.utils.function_calling import convert_to_openai_function

from .tools import get_tools
from .constants import REACT_ADDON, REACT_VARS, ALITA_ADDON, ALITA_VARS, LLAMA_ADDON, LLAMA_VARS
from .assistant import Assistant
from .prompt import AlitaPrompt
from .datasource import AlitaDataSource
from .artifact import Artifact
from .chat_message_template import Jinja2TemplatedChatMessagesTemplate
from ..agents.mixedAgentRenderes import conversation_to_messages

logger = logging.getLogger(__name__)

class AlitaClient:
    def __init__(self, base_url: str, project_id: int, auth_token: str):
        self.base_url = base_url.rstrip('/')
        self.api_path = '/api/v1'
        self.project_id = project_id
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}"
        }
        self.predict_url = f"{self.base_url}{self.api_path}/prompt_lib/predict/prompt_lib/{self.project_id}"
        self.prompt_versions = f"{self.base_url}{self.api_path}/prompt_lib/version/prompt_lib/{self.project_id}"
        self.prompts = f"{self.base_url}{self.api_path}/prompt_lib/prompt/prompt_lib/{self.project_id}"
        self.datasources = f"{self.base_url}{self.api_path}/datasources/datasource/prompt_lib/{self.project_id}"
        self.datasources_predict = f"{self.base_url}{self.api_path}/datasources/predict/prompt_lib/{self.project_id}"
        self.datasources_search = f"{self.base_url}{self.api_path}/datasources/search/prompt_lib/{self.project_id}"
        self.app = f"{self.base_url}{self.api_path}/applications/application/prompt_lib/{self.project_id}"
        self.application_versions = f"{self.base_url}{self.api_path}/applications/version/prompt_lib/{self.project_id}"
        self.integration_details = f"{self.base_url}{self.api_path}/integrations/integration/{self.project_id}"
        self.secrets_url = f"{self.base_url}{self.api_path}/secrets/secret/{self.project_id}"
        self.artifacts_url = f"{self.base_url}{self.api_path}/artifacts/artifacts/{self.project_id}"
        self.artifact_url = f"{self.base_url}{self.api_path}/artifacts/artifact/{self.project_id}"
        self.bucket_url = f"{self.base_url}{self.api_path}/artifacts/buckets/{self.project_id}"


    def prompt(self, prompt_id, prompt_version_id, chat_history=None, return_tool=False):
        url = f"{self.prompt_versions}/{prompt_id}/{prompt_version_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        model_settings = data['model_settings']
        messages = [SystemMessage(content=data['context'])]
        variables = {}
        if data['messages']:
            for message in data['messages']:
                if message.get('role') == 'assistant':
                    messages.append(AIMessage(content=message['content']))
                elif message.get('role') == 'user':
                    messages.append(HumanMessage(content=message['content']))
                else:
                    messages.append(SystemMessage(content=message['content']))
        if chat_history and isinstance(chat_history, list):
            messages.extend(chat_history)
        input_variables = []
        for variable in data['variables']:
            if variable['value']:
                variables[variable['name']] = variable['value']
            else:
                input_variables.append(variable['name'])
        template = Jinja2TemplatedChatMessagesTemplate(messages=messages)
        if input_variables and not variables:
            template.input_variables = input_variables
        if variables:
            template.partial_variables = variables
        if not return_tool:
            return template
        else:
            url = f"{self.prompts}/{prompt_id}"
            data = requests.get(url, headers=self.headers, verify=False).json()
            return AlitaPrompt(self, template, data['name'], data['description'], model_settings)

    def get_app_details(self, application_id: int):
        url = f"{self.app}/{application_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def get_app_version_details(self, application_id: int, application_version_id:int):
        url = f"{self.application_versions}/{application_id}/{application_version_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def get_integration_details(self, integration_id: str, format_for_model: bool = False):
        url = f"{self.integration_details}/{integration_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data

    def unsecret(self, secret_name: str):
        url = f"{self.secrets_url}/{secret_name}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        return data.get('secret', None)

    def application(self, client: Any, application_id: int, application_version_id: int,
                    tools: Optional[list] = None, chat_history: Optional[List[Any]] = None,
                    app_type=None):
        if tools is None:
            tools = []
        data = self.get_app_version_details(application_id, application_version_id)
        if not app_type:
            app_type = data.get("agent_type", "raw")
        if app_type == "react":
            data['instructions'] += REACT_ADDON
        elif app_type == "alita":
            data['instructions'] += ALITA_ADDON
        elif app_type == 'llama':
            data['instructions'] += LLAMA_ADDON
        messages = [SystemMessage(content=data['instructions'])]
        variables = {}
        input_variables = []
        for variable in data['variables']:
            if variable['value'] != "":
                variables[variable['name']] = variable['value']
            else:
                input_variables.append(variable['name'])
        if app_type == "react":
            input_variables = list(set(input_variables + REACT_VARS))
        elif app_type == "alita":
            input_variables = list(set(input_variables + ALITA_VARS))
        elif app_type == "llama":
            input_variables = list(set(input_variables + LLAMA_VARS))
        if chat_history and isinstance(chat_history, list):
            messages.extend(chat_history)
        template = Jinja2TemplatedChatMessagesTemplate(messages=messages)
        if input_variables and not variables:
            template.input_variables = input_variables
        if variables:
            template.partial_variables = variables
        tools = get_tools(client, data['tools'])
        if app_type == "dial":
            integration_details = self.get_integration_details(data['llm_settings']['integration_uid'])
            if integration_details['config']['is_shared']:
                api_key = environ.get('OPENAI_API_KEY')
            else:
                api_key = integration_details['settings']['api_token']['value']
                if integration_details['settings']['api_token']['from_secrets']:
                    api_key = self.unsecret(integration_details['settings']['api_token']['value'].split('.')[1][:-2])
            from langchain_openai import AzureChatOpenAI
            llm_client = AzureChatOpenAI(
                azure_endpoint=integration_details['settings']['api_base'],
                deployment_name=data['llm_settings']['model_name'],
                openai_api_version=integration_details['settings']['api_version'],
                openai_api_key=api_key,
                temperature=data['llm_settings']['temperature'],
                max_tokens=data['llm_settings']['max_tokens']
            )
            open_ai_funcs = [convert_to_openai_function(t) for t in tools]
            return Assistant(llm_client, template, tools, open_ai_funcs).getDialOpenAIAgentExecutor()
        elif app_type == "alita":
            return Assistant(client, template, tools).getAlitaExecutor()
        elif app_type == "llama":
            return Assistant(client, template, tools).getLLamaAgentExecutor()
        else:
            return Assistant(client, template, tools).getAgentExecutor()

    def datasource(self, datasource_id: int) -> AlitaDataSource:
        url = f"{self.datasources}/{datasource_id}"
        data = requests.get(url, headers=self.headers, verify=False).json()
        datasource_model = data['version_details']['datasource_settings']['chat']['chat_settings_embedding']
        chat_model = data['version_details']['datasource_settings']['chat']['chat_settings_ai']
        return AlitaDataSource(self, datasource_id, data["name"], data["description"],
                               datasource_model, chat_model)

    def assistant(self, prompt_id: int, prompt_version_id: int,
                  tools: list, openai_tools: Optional[Dict] = None,
                  client: Optional[Any] = None, chat_history: Optional[list] = None):
        prompt = self.prompt(prompt_id=prompt_id, prompt_version_id=prompt_version_id, chat_history=chat_history)
        return Assistant(client, prompt, tools, openai_tools)

    def artifact(self, bucket_name):
        return Artifact(self, bucket_name)


    def _process_requst(self, data):
        if data.status_code == 403:
            return { "error": "You are not authorized to access this resource"}
        elif data.status_code == 404:
            return { "error": "Resource not found"}
        elif data.status_code != 200:
            return {
                    "error": "An error occurred while fetching the resource",
                    "content": data.content
                    }
        else:
            return data.json()


    def bucket_exists(self, bucket_name):
        try:
            resp = self._process_requst(
                requests.get(f'{self.bucket_url}', headers=self.headers, verify=False)
            )
            for each in resp.get('rows', []):
                if each['name'] == bucket_name:
                    return True
            return False
        except:
            return False

    def create_bucket(self, bucket_name):
        post_data = {
            "name":bucket_name,
            "expiration_measure":"weeks",
            "expiration_value":"1"
        }
        resp = requests.post(f'{self.bucket_url}', headers=self.headers, json=post_data, verify=False)
        return self._process_requst(resp)


    def list_artifacts(self, bucket_name):
        url = f'{self.artifacts_url}/{bucket_name}'
        data = requests.get(url, headers=self.headers, verify=False)
        return self._process_requst(data)

    def create_artifact(self, bucket_name, artifact_name, artifact_data):
        url = f'{self.artifacts_url}/{bucket_name}'
        data = requests.post(url, headers=self.headers, files={
            'file': (artifact_name , artifact_data)
        }, verify=False)
        return self._process_requst(data)

    def download_artifact(self, bucket_name, artifact_name):
        url = f'{self.artifact_url}/{bucket_name}/{artifact_name}'
        data = requests.get(url, headers=self.headers, verify=False)
        if data.status_code == 403:
            return { "error": "You are not authorized to access this resource"}
        elif data.status_code == 404:
            return { "error": "Resource not found"}
        elif data.status_code != 200:
            return {
                    "error": "An error occurred while fetching the resource",
                    "content": data.content
                    }
        return data.content

    def delete_artifact(self, bucket_name, artifact_name):
        url = f'{self.artifact_url}/{bucket_name}/{artifact_name}'
        data = requests.delete(url, headers=self.headers, verify=False)
        return self._process_requst(data)

    def _prepare_messages(self, messages: list[BaseMessage]):
        chat_history = []
        for message in messages:
            if message.type == 'human':
                chat_history.append({
                    'role': 'user',
                    'content': message.content
                })
            elif message.type == 'system':
                chat_history.append({
                    'role': 'system',
                    'content': message.content
                })
            else:
                chat_history.append({
                    'role': 'assistant',
                    'content': message.content
                })
        return chat_history

    def _prepare_payload(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict]):
        chat_history = self._prepare_messages(messages)
        if not variables:
            variables = []
        return {
            "type": "chat",
            "project_id": self.project_id,
            "context": '',
            "model_settings": model_settings,
            "user_input": '',
            "chat_history": chat_history,
            "variables": variables,
            "format_response": True
        }

    def async_predict(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict] = None):
        # TODO: Modify to make it appropriate stream response
        prompt_data = self._prepare_payload(messages, model_settings, variables)
        response = requests.post(self.predict_url, headers=self.headers, json=prompt_data, verify=False)
        logger.info(response.content)
        response_data = response.json()
        for message in response_data['messages']:
            if message.get('role') == 'user':
                yield HumanMessage(content=message['content'])
            else:
                yield AIMessage(content=message['content'])

    def predict(self, messages: list[BaseMessage], model_settings: dict, variables: list[dict] = None):
        prompt_data = self._prepare_payload(messages, model_settings, variables)

        response = requests.post(self.predict_url, headers=self.headers, json=prompt_data, verify=False)
        if response.status_code != 200:
            logger.error("Error in response of predict: {response.content}")
            raise requests.exceptions.HTTPError(response.content)
        try:
            response_data = response.json()
            response_messages = []
            print(response_data['messages'])
            for message in response_data['messages']:
                if message.get('type') == 'user':
                    response_messages.append(HumanMessage(content=message['content']))
                else:
                    response_messages.append(AIMessage(content=message['content']))
            return response_messages
        except TypeError:
            logger.error(f"TypeError in response of predict: {response.content}")
            raise

    def rag(self, datasource_id: int, messages: list[BaseMessage],
            datasource_settings: dict, datasource_predict_settings: dict):
        chat_history = self._prepare_messages(messages)
        data = {
            "input": '',
            "context": '',
            "chat_history": chat_history,
            "chat_settings_ai": datasource_predict_settings,
            "chat_settings_embedding": datasource_settings
        }
        headers = self.headers | {"Content-Type": "application/json"}
        response = requests.post(f"{self.datasources_predict}/{datasource_id}", headers=headers, json=data, verify=False).json()
        return AIMessage(content=response['response'], additional_kwargs={"references": response['references']})

    def search(self, datasource_id: int, messages: list[BaseMessage], datasource_settings: dict) -> AIMessage:
        chat_history = self._prepare_messages(messages)
        user_input = ''
        for message in chat_history[::-1]:
            if message['role'] == 'user':
                user_input = message['content']
                break
        data = {
            "chat_history": [
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "chat_settings_embedding": datasource_settings,
            "str_content": True
        }
        headers = self.headers | {"Content-Type": "application/json"}
        response = requests.post(f"{self.datasources_search}/{datasource_id}", headers=headers, json=data, verify=False)
        if not response.ok:
            raise Exception(f'Search request failed with code {response.status_code}')
        resp_data = response.json()
        # content = "\n\n".join([finding["page_content"] for finding in response["findings"]])
        content = resp_data["findings"]
        references = resp_data['references']
        return AIMessage(content=content, additional_kwargs={"references": references})
