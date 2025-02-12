import frappe
import logging
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunRealtimeReportRequest,
    Dimension,
    Metric,
)
from google.oauth2 import service_account
from frappe.utils import now_datetime


def fetch_daily_visitor_location_total():
    
    
    # Retrieve credentials from site_config.json
    credentials_info = frappe.get_site_config().get('google_analytics_credentials')
    if not credentials_info:
        frappe.throw("Google Analytics credentials not found in site_config.json")

    # Create credentials using google.oauth2
    credentials = service_account.Credentials.from_service_account_info(credentials_info)

    # Initialize the Analytics Data API client
    client = BetaAnalyticsDataClient(credentials=credentials)

    # Define your GA4 Property ID
    property_id = '475318176'  # Replace with your actual GA4 Property ID

    # Build the Real-time API request (remove city dimension)
    request = RunRealtimeReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="country")],  # Only country dimension
        metrics=[Metric(name="activeUsers")],
    )

    try:
        # Fetch data from Google Analytics
        response = client.run_realtime_report(request)
        frappe.logger().info(f"Google Analytics Real-time API response: {response}")
    except Exception as e:
        frappe.log_error(message=str(e), title="Google Analytics Data API Error")
        frappe.throw("An error occurred while fetching real-time data from Google Analytics.")

    # Check if response contains data
    if not response.rows:
        frappe.logger().info("No data returned from Google Analytics Real-time API.")
        frappe.msgprint("No data returned from Google Analytics Real-time API.")
        return

    # Process and store the data
    process_daily_response_total(response)


def process_daily_response_total(response):
    """Process the fetched data and store it for today."""
    today_date = now_datetime().strftime('%Y-%m-%d')  # Store the data with date (no time)
    total_users_by_country = {}

    # Aggregate active users by country
    for row in response.rows:
        country = row.dimension_values[0].value
        active_users = int(row.metric_values[0].value)

        if country in total_users_by_country:
            total_users_by_country[country] += active_users
        else:
            total_users_by_country[country] = active_users

        frappe.logger().info(f"Country={country}, Active Users={active_users}")

    # Process and store the total active users per country for today
    for country, total_active_users in total_users_by_country.items():
        # Check if record already exists for this country and date
        existing_record = frappe.get_all('Visitor Total view', filters={
            'date': today_date,
            'country': country
        }, fields=['name', 'users'])

        if existing_record:
            # Update existing record by adding new active users to existing count
            doc = frappe.get_doc('Visitor Total view', existing_record[0].name)
            doc.users += total_active_users  # Add new users to the existing total
            try:
                doc.save()
                frappe.logger().info(f"Updated existing Visitor Location: {doc.name} with new users count")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Updating Visitor Location")
        else:
            # Create new record
            doc = frappe.get_doc({
                'doctype': 'Visitor Total view',
                'country': country,
                'users': total_active_users,
                'date': today_date  # Store the date
            })
            try:
                doc.insert()
                frappe.logger().info(f"Inserted new Visitor Location: {doc.name}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Inserting Visitor Location")

    frappe.db.commit()


