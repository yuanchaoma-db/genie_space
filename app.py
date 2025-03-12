import dash
from dash import html, dcc, Input, Output, State, callback, ALL, MATCH, callback_context, no_update, clientside_callback, dash_table
import dash_bootstrap_components as dbc
import json
from genie_room import genie_query
import pandas as pd

app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)

# Define the layout
app.layout = html.Div([
    # Top navigation bar
    html.Div([
        # Left component containing both nav-left and sidebar
        html.Div([
            # Nav left
            html.Div([
                html.Button([
                    html.Img(src="assets/menu_icon.svg", className="menu-icon")
                ], id="sidebar-toggle", className="nav-button"),
                # Speech icon in top nav (visible when sidebar is closed)
                html.Button([
                    html.Img(src="assets/plus_icon.svg", className="new-chat-icon")
                ], id="new-chat-button", className="nav-button",disabled=False),
                html.Button([
                    html.Img(src="assets/plus_icon.svg", className="new-chat-icon"),
                    html.Div("New chat", className="new-chat-text")
                ], id="sidebar-new-chat-button", className="new-chat-button",disabled=False)
            ], id="nav-left", className="nav-left"),
            
            # Sidebar (now inside the left component)
            html.Div([
                html.Div([
                    html.Div("Your conversations with Genie", className="sidebar-header-text"),
                ], className="sidebar-header"),
                html.Div([], className="chat-list", id="chat-list")
            ], id="sidebar", className="sidebar")
        ], id="left-component", className="left-component"),
        
        html.Div([
            html.Div("Genie Space", id="logo-container", className="logo-container")
        ], className="nav-center"),
        html.Div([
            html.Div("S", className="user-avatar")
        ], className="nav-right")
    ], className="top-nav"),
    
    # Main content area with chat
    html.Div([
        # Main chat area
        html.Div([
            # Chat content
            html.Div([
                # Initial welcome message
                html.Div([
                    html.Div([html.Div([
                    html.Div(className="genie-logo")
                ], className="genie-logo-container")],
                className="genie-logo-container-header"),
               
                    html.Div("Supply Chain Optimization", className="welcome-message"),
                
                    html.Div("Analyze your Supply Chain Performance leveraging AI/BI Dashboard. Deep dive into your data and metrics.", 
                             className="welcome-message-description"),
                    
                    # Suggestion buttons with IDs
                    html.Div([
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Span("What tables are there and how are they connected? Give me a short summary.")
                        ], id="suggestion-1", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Span("What is the trend of my sales for the last 3 months?")
                        ], id="suggestion-2", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Span("Explain the dataset")
                        ], id="suggestion-3", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Span("What was the demand for our products by week in 2024?")
                        ], id="suggestion-4", className="suggestion-button")
                    ], className="suggestion-buttons")
                ], id="welcome-container", className="welcome-container visible"),
                
                # Chat messages will be added here
                html.Div([],id="chat-messages", className="chat-messages"),
                
            ], id="chat-content", className="chat-content"),
            
            # Fixed chat input at bottom (for after initial message is sent)
            html.Div([
                html.Div([
                    dcc.Input(
                        id="chat-input-fixed",
                        placeholder="Ask your question...",
                        className="chat-input",
                        type="text",
                        disabled=False
                    ),
                    html.Div([
                        html.Button(
                            id="send-button-fixed", 
                            className="input-button send-button",
                            disabled=False
                        )
                    ], className="input-buttons-right"),
                    # Add this tooltip div
                    html.Div("You can only submit one query at a time", 
                            id="query-tooltip", 
                            className="query-tooltip hidden")
                ], id="fixed-input-container", className="fixed-input-container"),
                
                html.Div("Always review the accuracy of responses.", className="disclaimer-fixed")
            ], id="fixed-input-wrapper", className="fixed-input-wrapper"),
            
        ], id="chat-container", className="chat-container"),
        
    ], id="main-content", className="main-content"),
    
    # Add these new components
    html.Div(id='dummy-output'),
    dcc.Store(id="chat-trigger", data={"trigger": False, "message": ""}),
    dcc.Store(id="chat-history-store", data=[]),
    dcc.Store(id="query-running-store", data=False)
])

# Store chat history
chat_history = []

# First callback: Handle inputs and show thinking indicator
@app.callback(
    [Output("chat-messages", "children"),
     Output("chat-input-fixed", "value"),
     Output("welcome-container", "className"),
     Output("chat-trigger", "data"),
     Output("query-running-store", "data"),
     Output("chat-list", "children"),
     Output("chat-history-store", "data")],
    [Input("send-button-fixed", "n_clicks"),
     Input("chat-input-fixed", "n_submit"),
     Input("suggestion-1", "n_clicks"),
     Input("suggestion-2", "n_clicks"),
     Input("suggestion-3", "n_clicks"),
     Input("suggestion-4", "n_clicks")],
    [State("chat-input-fixed", "value"),
     State("chat-messages", "children"),
     State("welcome-container", "className"),
     State("chat-list", "children"),
     State("chat-history-store", "data")],
    prevent_initial_call=True
)
def handle_all_inputs(n_clicks, n_submit, s1, s2, s3, s4, input_value, current_messages, 
                     welcome_class, current_chat_list, chat_history):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Handle suggestion buttons
    suggestion_messages = {
        "suggestion-1": "What tables are there and how are they connected? Give me a short summary.",
        "suggestion-2": "What is the trend of my sales for the last 3 months?",
        "suggestion-3": "Explain the dataset",
        "suggestion-4": "What was the demand for our products by week in 2024?"
    }
    
    # Get the user input based on what triggered the callback
    if trigger_id in suggestion_messages:
        user_input = suggestion_messages[trigger_id]
    else:
        user_input = input_value
    
    if not user_input:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Create user message
    user_message = html.Div([
        html.Div([
            html.Div("S", className="user-avatar"),
            html.Span("Sophie", className="model-name")
        ], className="user-info"),
        html.Div(user_input, className="message-text")
    ], className="user-message message")
    
    # Add the user message to the chat
    if current_messages:
        # If we have existing messages, append to them
        updated_messages = current_messages + [user_message]
    else:
        # If no messages, start new conversation
        updated_messages = [user_message]
    
    # Add thinking indicator
    thinking_indicator = html.Div([
        html.Div([
            html.Span(className="spinner"),
            html.Span("Thinking...")
        ], className="thinking-indicator")
    ], className="bot-message message")
    
    updated_messages.append(thinking_indicator)
    
    # Add new query to the sidebar chat list with active class
    new_chat_item = html.Div(user_input, 
                            className="chat-item active", 
                            id={"type": "chat-item", "index": 0})
    
    # Update existing items to remove active class and update indices
    updated_chat_list = [new_chat_item] + [
        html.Div(
            item["props"]["children"],
            className="chat-item",
            id={"type": "chat-item", "index": i + 1}
        )
        for i, item in enumerate(current_chat_list)
    ]
    
    # Update chat history
    if chat_history is None:
        chat_history = []
        
    new_chat_history = [{
            "query": user_input,
            "messages": updated_messages 
        }] + chat_history
    
    # Set the trigger data with new message
    trigger_data = {"trigger": True, "message": user_input}
    return (updated_messages, "", "welcome-container hidden", 
            trigger_data, True, updated_chat_list, new_chat_history)


# Second callback: Make API call and show response
@app.callback(
    [Output("chat-messages", "children", allow_duplicate=True),
     Output("chat-history-store", "data", allow_duplicate=True),
     Output("chat-trigger", "data", allow_duplicate=True),
     Output("query-running-store", "data", allow_duplicate=True)],
    [Input("chat-trigger", "data")],
    [State("chat-messages", "children"),
     State("chat-history-store", "data")],
    prevent_initial_call=True
)
def get_model_response(trigger_data, current_messages, chat_history):
    if not trigger_data or not trigger_data.get("trigger"):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    user_input = trigger_data.get("message", "")
    if not user_input:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    try:
        response = genie_query(user_input)
        
        if isinstance(response, str):
            response = response.replace("`", "")
            content = dcc.Markdown(response, className="message-text")
        else:
            # Data table response
            df = pd.DataFrame(response)
            
            # Store the dataframe as JSON in a hidden div
            table_id = f"table-{len(chat_history)}"
            
            # Create the table with adjusted styles
            data_table = dash_table.DataTable(
                id=table_id,
                data=df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in df.columns],
                
                # Export configuration
                export_format="csv",
                export_headers="display",
                
                # Other table properties
                page_size=10,
                style_table={
                    'display': 'inline-block',
                    'overflowX': 'auto',
                    'width': '95%',
                    'marginRight': '20px'
                },
                style_cell={
                    'textAlign': 'left',
                    'fontSize': '12px',
                    'padding': '4px 10px',
                    'fontFamily': '-apple-system, BlinkMacSystemFont,Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif',
                    'backgroundColor': 'transparent',
                    'maxWidth': 'fit-content',
                    'minWidth': '100px'
                },
                style_header={
                    'backgroundColor': '#f8f9fa',
                    'fontWeight': '600',
                    'borderBottom': '1px solid #eaecef'
                },
                style_data={
                    'whiteSpace': 'normal',
                    'height': 'auto'
                },
                fill_width=False,
                page_current=0,
                page_action='native'
            )
            
            # Use the built-in export functionality of DataTable
            content = html.Div([
                html.Div([data_table], style={
                    'marginBottom': '20px',
                    'paddingRight': '5px'
                }),
                html.Div("Click the export button in the table header to download as CSV", 
                         style={"fontSize": "12px", "color": "#666", "marginTop": "-15px", "marginBottom": "10px"})
            ])
        
        # Create bot response
        bot_response = html.Div([
            html.Div([
                html.Div(className="model-avatar"),
                html.Span("Genie", className="model-name")
            ], className="model-info"),
            html.Div([
                content,
                html.Div([
                    html.Div([
                        
                        html.Button(
                            id={"type": "thumbs-up-button", "index": len(chat_history)},
                            className="thumbs-up-button"
                        ),
                        html.Button(
                            id={"type": "thumbs-down-button", "index": len(chat_history)},
                            className="thumbs-down-button"
                        )
                    ], className="message-actions")
                ], className="message-footer")
            ], className="message-content")
        ], className="bot-message message")
        
        # Update chat history with both user message and bot response
        if chat_history and len(chat_history) > 0:
            chat_history[0]["messages"] = current_messages[:-1] + [bot_response]  
        return current_messages[:-1] + [bot_response], chat_history, {"trigger": False, "message": ""}, False
        
    except Exception as e:
        error_msg = f"Sorry, I encountered an error: {str(e)}"
        error_response = html.Div([
            html.Div([
                html.Div(className="model-avatar"),
                html.Span("Genie", className="model-name")
            ], className="model-info"),
            html.Div([
                html.Div(error_msg, className="message-text")
            ], className="message-content")
        ], className="bot-message message")
        
        # Update chat history with both user message and error response
        if chat_history and len(chat_history) > 0:
            chat_history[0]["messages"] = current_messages[:-1] + [error_response]
        
        return current_messages[:-1] + [error_response], chat_history, {"trigger": False, "message": ""}, False

# Toggle sidebar and speech button
@app.callback(
    [Output("sidebar", "className"),
     Output("new-chat-button", "style"),
     Output("sidebar-new-chat-button", "style"),
     Output("logo-container", "className"),
     Output("nav-left", "className"),
     Output("left-component", "className"),
     Output("main-content", "className")],
    [Input("sidebar-toggle", "n_clicks")],
    [State("sidebar", "className"),
     State("left-component", "className"),
     State("main-content", "className")]
)
def toggle_sidebar(n_clicks, current_sidebar_class, current_left_component_class, current_main_content_class):
    if n_clicks:
        if "sidebar-open" in current_sidebar_class:
            # Sidebar is closing
            return "sidebar", {"display": "flex"}, {"display": "none"}, "logo-container", "nav-left", "left-component", "main-content"
        else:
            # Sidebar is opening
            return "sidebar sidebar-open", {"display": "none"}, {"display": "flex"}, "logo-container logo-container-open", "nav-left nav-left-open", "left-component left-component-open", "main-content main-content-shifted"
    # Initial state
    return current_sidebar_class, {"display": "flex"}, {"display": "none"}, "logo-container", "nav-left", "left-component", current_main_content_class

# Add callback for chat item selection
@app.callback(
    [Output("chat-messages", "children", allow_duplicate=True),
     Output("welcome-container", "className", allow_duplicate=True),
     Output("chat-list", "children", allow_duplicate=True)],
    [Input({"type": "chat-item", "index": ALL}, "n_clicks")],
    [State("chat-history-store", "data"),
     State("chat-list", "children")],
    prevent_initial_call=True
)
def show_chat_history(n_clicks, chat_history, current_chat_list):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    # Get the clicked item index
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    clicked_index = json.loads(triggered_id)["index"]
    
    if not chat_history or clicked_index >= len(chat_history):
        return dash.no_update, dash.no_update, dash.no_update
    
    # Find the clicked query in chat history
    clicked_query = current_chat_list[clicked_index]["props"]["children"]
    chat_data = None
    
    # Find matching history item by query text
    for item in chat_history:
        if item["query"] == clicked_query:
            chat_data = item
            break
    
    if not chat_data:
        return dash.no_update, dash.no_update, dash.no_update
    
    # Update active state in chat list
    updated_chat_list = []
    for i, item in enumerate(current_chat_list):
        new_class = "chat-item active" if i == clicked_index else "chat-item"
        updated_chat_list.append(
            html.Div(
                item["props"]["children"],
                className=new_class,
                id={"type": "chat-item", "index": i}
            )
        )
    return chat_data["messages"], "welcome-container hidden", updated_chat_list

# Modify the clientside callback to target the chat-container
app.clientside_callback(
    """
    function(children) {
        var chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        return '';
    }
    """,
    Output('dummy-output', 'children'),
    Input('chat-messages', 'children'),
    prevent_initial_call=True
)

# Modify the new chat button callback to maintain the sidebar chat list
@app.callback(
    [Output("welcome-container", "className", allow_duplicate=True),
     Output("chat-messages", "children", allow_duplicate=True),
     Output("chat-trigger", "data", allow_duplicate=True),
     Output("query-running-store", "data", allow_duplicate=True),
     Output("chat-history-store", "data", allow_duplicate=True)],
    [Input("new-chat-button", "n_clicks"),
     Input("sidebar-new-chat-button", "n_clicks")],
    [State("chat-messages", "children"),
     State("chat-trigger", "data"),
     State("chat-history-store", "data"),
     State("chat-list", "children"),
     State("query-running-store", "data")],
    prevent_initial_call=True
)
def reset_to_welcome(n_clicks1, n_clicks2, chat_messages, chat_trigger, chat_history_store, chat_list, query_running):
    # Reset the chat window but keep sidebar intact
    if query_running and chat_trigger.get("trigger") and chat_history_store:
        # check if the last message is a thinking indicator
        chat_history_store[0]["messages"] = chat_history_store[0]["messages"][:-1]
    return "welcome-container visible", [], {"trigger": False, "message": ""}, False, chat_history_store
    

@app.callback(
    [Output("welcome-container", "className", allow_duplicate=True)],
    [Input("chat-messages", "children")],
    prevent_initial_call=True
)
def reset_query_running(chat_messages):
    # Return as a single-item list
    if chat_messages:
        return ["welcome-container hidden"]
    else:
        return ["welcome-container visible"]

# Add callback to disable input while query is running
@app.callback(
    [Output("chat-input-fixed", "disabled"),
     Output("send-button-fixed", "disabled"),
     Output("new-chat-button", "disabled"),
     Output("sidebar-new-chat-button", "disabled"),
     Output("query-tooltip", "className")],
    [Input("query-running-store", "data")],
    prevent_initial_call=True
)
def toggle_input_disabled(query_running):
    # Show tooltip when query is running, hide it otherwise
    tooltip_class = "query-tooltip visible" if query_running else "query-tooltip hidden"
    
    # Disable input and buttons when query is running
    return query_running, query_running, query_running, query_running, tooltip_class


# Fix the callback for thumbs up/down buttons
@app.callback(
    [Output({"type": "thumbs-up-button", "index": MATCH}, "className"),
     Output({"type": "thumbs-down-button", "index": MATCH}, "className")],
    [Input({"type": "thumbs-up-button", "index": MATCH}, "n_clicks"),
     Input({"type": "thumbs-down-button", "index": MATCH}, "n_clicks")],
    [State({"type": "thumbs-up-button", "index": MATCH}, "className"),
     State({"type": "thumbs-down-button", "index": MATCH}, "className")],
    prevent_initial_call=True
)
def handle_feedback(up_clicks, down_clicks, up_class, down_class):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    button_type = json.loads(trigger_id)["type"]
    
    if button_type == "thumbs-up-button":
        # Toggle thumbs up, remove thumbs down if active
        new_up_class = "thumbs-up-button active" if "active" not in up_class else "thumbs-up-button"
        new_down_class = "thumbs-down-button"
    else:
        # Toggle thumbs down, remove thumbs up if active
        new_up_class = "thumbs-up-button"
        new_down_class = "thumbs-down-button active" if "active" not in down_class else "thumbs-down-button"
    
    return new_up_class, new_down_class

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
