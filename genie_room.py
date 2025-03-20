import pandas as pd
import time
import requests
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List, Union, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Load environment variables
SPACE_ID = os.environ.get("SPACE_ID")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")

class GenieClient:
    def __init__(self, host: str, token: str, space_id: str):

        self.host = host
        self.token = token
        self.space_id = space_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.base_url = f"https://{host}/api/2.0/genie/spaces/{space_id}"
    

    def start_conversation(self, question: str) -> Dict[str, Any]:
        """
        Start a new conversation with the given question.
        
        Returns:
            Dictionary containing conversation_id, message_id, and other metadata
        """
        url = f"{self.base_url}/start-conversation"
        payload = {"content": question}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
                
            return result
        except Exception as e:
            logger.error(f"Failed to start conversation: {str(e)}")
            raise

    def send_message(self, conversation_id: str, message: str) -> Dict[str, Any]:
        """
        Send a follow-up message to an existing conversation.
        
        Args:
            conversation_id: The ID of the conversation
            message: The message content to send
            
        Returns:
            Dictionary containing message_id and other metadata
        """
        url = f"{self.base_url}/conversations/{conversation_id}/messages"
        payload = {"content": message}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return result
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            raise

    def get_message(self, conversation_id: str, message_id: str) -> Dict[str, Any]:
        """
        Get the details of a specific message.
        
        Args:
            conversation_id: The ID of the conversation
            message_id: The ID of the message
            
        Returns:
            Dictionary containing message details
        """
        url = f"{self.base_url}/conversations/{conversation_id}/messages/{message_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            return result
        except Exception as e:
            logger.error(f"Failed to get message: {str(e)}")
            raise

    def get_query_result(self, conversation_id: str, message_id: str, attachment_id: str) -> Dict[str, Any]:
        """
        Get the query result using the new attachment_id endpoint.
        
        Args:
            conversation_id: The ID of the conversation
            message_id: The ID of the message
            attachment_id: The ID of the attachment
            
        Returns:
            Dictionary containing query results
        """
        url = f"{self.base_url}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            # Extract data_array from the correct nested location
            data_array = []
            if 'statement_response' in result:
                if 'result' in result['statement_response']:
                    data_array = result['statement_response']['result'].get('data_array', [])
                
            return {
                'data_array': data_array,
                'schema': result.get('statement_response', {}).get('manifest', {}).get('schema', {})
            }
        except Exception as e:
            logger.error(f"Failed to get query result: {str(e)}")
            raise

    def execute_query(self, conversation_id: str, message_id: str, attachment_id: str) -> Dict[str, Any]:
        """
        Execute a query using the new attachment_id endpoint.
        
        Args:
            conversation_id: The ID of the conversation
            message_id: The ID of the message
            attachment_id: The ID of the attachment
            
        Returns:
            Dictionary containing execution results
        """
        url = f"{self.base_url}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/execute-query"
        
        
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()

            return result
        except Exception as e:
            logger.error(f"Failed to execute query: {str(e)}")
            raise

    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages in a conversation.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            List of message dictionaries
        """
        url = f"{self.base_url}/conversations/{conversation_id}/messages"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def wait_for_message_completion(self, conversation_id: str, message_id: str, timeout: int = 300, poll_interval: int = 2) -> Dict[str, Any]:
        """
        Wait for a message to reach a terminal state (COMPLETED, ERROR, etc.).
        
        Args:
            conversation_id: The ID of the conversation
            message_id: The ID of the message
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds
            
        Returns:
            The completed message
        """
        
        start_time = time.time()
        attempt = 1
        
        while time.time() - start_time < timeout:
            
            message = self.get_message(conversation_id, message_id)
            status = message.get("status")
            
            if status in ["COMPLETED", "ERROR", "FAILED"]:
                return message
                
            time.sleep(poll_interval)
            attempt += 1
            
        raise TimeoutError(f"Message processing timed out after {timeout} seconds")

def genie_query(question: str) -> Union[str, pd.DataFrame]:
    """
    Send a question to Genie and return either:
    - Text response if text content is available
    - DataFrame if query result is available
    """
    client = GenieClient(
        host=DATABRICKS_HOST,
        token=DATABRICKS_TOKEN,
        space_id=SPACE_ID
    )
    
    # Start conversation and wait for completion
    response = client.start_conversation(question)
    conversation_id = response.get("conversation_id")
    message_id = response.get("message_id")
    complete_message = client.wait_for_message_completion(conversation_id, message_id)
    
    # Check attachments first
    attachments = complete_message.get("attachments", [])
    for attachment in attachments:
        attachment_id = attachment.get("attachment_id")
        
        # If there's text content in the attachment, return it
        if "text" in attachment and "content" in attachment["text"]:
            return attachment["text"]["content"]
        
        # If there's a query, get the result
        elif "query" in attachment:
            query_result = client.get_query_result(conversation_id, message_id, attachment_id)
            data_array = query_result.get('data_array', [])
            schema = query_result.get('schema', {})
            columns = [col.get('name') for col in schema.get('columns', [])]
            
            # If we have data, return as DataFrame
            if data_array:
                # If no columns from schema, create generic ones
                if not columns and data_array and len(data_array) > 0:
                    columns = [f"column_{i}" for i in range(len(data_array[0]))]
                
                df = pd.DataFrame(data_array, columns=columns)
                return df
    
    # If no attachments or no data in attachments, return text content
    if 'content' in complete_message:
        return complete_message.get('content', '')
    
    return "No response available"

