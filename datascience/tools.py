
"""
Tools for invoking the Data Science Agent from BigQuery Agent
"""

from google.adk.tools import Tool, ToolContext
from google.adk.tools.agent_tool import AgentTool
import logging

logger = logging.get_logger(__name__)

# Import will be done lazily to avoid circular imports
_datascience_agent = None

def get_datascience_agent():
    """Lazy load the data science agent to avoid circular imports"""
    global _datascience_agent
    if _datascience_agent is None:
        from datascience_agent.agent import root_agent
        _datascience_agent = root_agent
    return _datascience_agent

@Tool()
async def call_datascience_agent(
    question: str,
    tool_context: ToolContext,
) -> dict:
    """
    Call the Data Science Agent for advanced analytics and visualization.

    Use this tool when the user asks for:
    - Forecasting or predictions
    - Trend analysis
    - Statistical analysis (correlation, distribution, regression)
    - Anomaly detection
    - Data visualization (charts, graphs, plots)
    - Pattern identification
    - Advanced metrics calculation

    The data science agent will receive any data from previous BigQuery
    queries stored in tool_context.state['bigquery_query_result'].

    Args:
        question: The analytics question or visualization request
        tool_context: Context containing data from previous queries

    Returns:
        Analysis results including insights and visualizations

    Examples:
        - "Plot order trend for location 6777 over last 30 days"
        - "Forecast next week's order volume"
        - "Detect anomalies in transmission patterns"
        - "Calculate correlation between ship dates and destinations"
        - "Show distribution of orders by location"
    """
    logger.info(f"Calling Data Science Agent: {question}")

    # Check if we have data to analyze
    bigquery_data = tool_context.state.get('bigquery_query_result', None)

    if not bigquery_data:
        return {
            "status": "error",
            "message": "No data available for analysis. Please run a BigQuery query first to retrieve data."
        }

# Prepare question with data context
question_with_data = f"""
Question to answer: {question}

Data to analyze is available in the following format:
<BIGQUERY_DATA>
{bigquery_data}
</BIGQUERY_DATA>

Perform the requested analysis on this data and provide:
1. Key findings and metrics
2. Visualizations if applicable
3. Insights and recommendations
"""

    try:
        # Get the data science agent
        ds_agent = get_datascience_agent()

        # Create agent tool
        agent_tool = AgentTool(agent=ds_agent)

        # Call the data science agent
        response = await agent_tool.run_async(
            args={"request": question_with_data},
            tool_context=tool_context
        )

        # Store response in context for potential follow-up questions
        tool_context.state['datascience_agent_output'] = response

        logger.info("Data Science Agent completed successfully")
        return {
            "status": "success",
            "analysis": response
        }

    except Exception as e:
        logger.error(f"Error calling Data Science Agent: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to perform analysis: {str(e)}"
        }

# Decision helper for when to use data science agent
def should_use_datascience_agent(query: str) -> bool:
    """
    Determine if a query should be routed to the data science agent.

    Args:
        query: The user's query

    Returns:
        True if query requires advanced analytics
    """
    analytics_keywords = [
        'forecast', 'predict', 'trend', 'pattern', 'anomaly',
        'correlation', 'distribution', 'plot', 'chart', 'graph',
        'visualize', 'analyze', 'statistical', 'regression',
        'time series', 'moving average', 'standard deviation',
        'outlier', 'seasonal', 'growth rate'
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in analytics_keywords)