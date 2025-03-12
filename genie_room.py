import pandas as pd
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def start_conversation(space_id, question, auth_token):
    """
    Starts a new conversation with the given question.
    """
    url = f"{os.getenv('DATABRICKS_HOST')}/api/2.0/genie/spaces/{space_id}/start-conversation"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    payload = {
        "content": question
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Failed to start conversation, status code: {response.status_code}")
    data = response.json()
    return {
        'message_id': data['message_id'],
        'conversation_id': data['conversation_id']
    }

def add_message_to_conversation(space_id, conversation_id, question, auth_token):
    """
    Adds a new message to an existing conversation.
    """
    url = f"{os.getenv('DATABRICKS_HOST')}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    payload = {
        "content": question
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Failed to add message to conversation, status code: {response.status_code}")
    data = response.json()
    return {
        'message_id': data['id'],
        'conversation_id': data['conversation_id']
    }

def get_query_message(space_id, conversation_id, message_id, auth_token):
    """
    Retrieves the query results for a given message.
    """
    url = f"{os.getenv('DATABRICKS_HOST')}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get query message, status code: {response.status_code}")
    return response.json()

def get_query_results(space_id, conversation_id, message_id, auth_token):
    """
    Retrieves the query results for a given message.
    """
    url = f"{os.getenv('DATABRICKS_HOST')}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/query-result"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get query results, status code: {response.status_code}")
    return response.json()

def process_query_result(result):
    """
    Processes the query result and returns a pandas DataFrame.
    """
    statement_response = result.get('statement_response', {})
    if statement_response.get('status', {}).get('state') != 'SUCCEEDED':
        raise Exception("Query execution failed or is still in progress")

    manifest = statement_response.get('manifest', {})
    schema = manifest.get('schema', {})
    columns = [col['name'] for col in schema.get('columns', [])]

    data = statement_response.get('result', {}).get('data_typed_array', [])
    rows = [[c.get('str', "") for c in r['values']] for r in data]

    return pd.DataFrame(rows, columns=columns)

def query_data(space_id, question, auth_token, conversation_id=None, max_retries=10, retry_interval=5):
    """
    Queries the outage data using the given question.
    """
    if conversation_id:
        conversation = add_message_to_conversation(space_id, conversation_id, question, auth_token)
    else:
        conversation = start_conversation(space_id, question, auth_token)
    message_id = conversation['message_id']
    conversation_id = conversation['conversation_id']

    for _ in range(max_retries):
        message = get_query_message(space_id, conversation_id, message_id, auth_token)
        if message.get('status', {}) == 'COMPLETED':
            # Check if there's a query object in attachments
            attachments = message.get('attachments', [])
            query_object = next((att.get('query') for att in attachments if 'query' in att), None)

            if query_object:
                result = get_query_results(space_id, conversation_id, message_id, auth_token)
                if result.get('statement_response', {}).get('status', {}).get('state', "") == 'SUCCEEDED':
                    df = process_query_result(result)
                    return df, conversation_id
            else:
                # If no query object, return the content of the text object
                text_object = next((att.get('text', {}).get('content') for att in attachments if 'text' in att), None)
                if text_object:
                    return text_object, conversation_id
        
        time.sleep(retry_interval)

    raise Exception("Query execution timed out")


class ConversationContext:
    def __init__(self):
        self.conversation_id = None
        self.space_id = os.getenv("SPACE_ID")
        self.auth_token = os.getenv("DATABRICKS_TOKEN")

conversation_context = ConversationContext()

def genie_query(question):
    global conversation_context
    result, conversation_id = query_data(conversation_context.space_id, question, conversation_context.auth_token, conversation_context.conversation_id)
    conversation_context.conversation_id = conversation_id
    return result
