import frappe
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunRealtimeReportRequest,
    Dimension,
    Metric,
)
from google.oauth2 import service_account
from frappe.utils import now_datetime


def fetch_realtime_visitor_location():
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


    # Build the Real-time API request
    request = RunRealtimeReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="country"), Dimension(name="city")],
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
    process_realtime_response(response)


def process_realtime_response(response):
    timestamp = now_datetime().strftime('%Y-%m-%d %H:%M:%S')
    for row in response.rows:
        country = row.dimension_values[0].value
        city = row.dimension_values[1].value
        active_users = int(row.metric_values[0].value)


        frappe.logger().info(f"Processing row: Country={country}, City={city}, Active Users={active_users}")


        # Check if record already exists for this timestamp, country, and city
        existing_record = frappe.get_all('Visitor Location', filters={
            'timestamp': timestamp,
            'country': country,
            'city': city
        }, fields=['name'])


        if existing_record:
            # Update existing record
            doc = frappe.get_doc('Visitor Location', existing_record[0].name)
            doc.users = active_users
            try:
                doc.save()
                frappe.logger().info(f"Updated existing Visitor Location: {doc.name}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Updating Visitor Location")
        else:
            # Create new record
            doc = frappe.get_doc({
                'doctype': 'Visitor Location',
                'country': country,
                'city': city,
                'users': active_users,
                'timestamp': timestamp
            })
            try:
                doc.insert()
                frappe.logger().info(f"Inserted new Visitor Location: {doc.name}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Inserting Visitor Location")


    frappe.db.commit()

