import frappe
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest 
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
)
from google.oauth2 import service_account
from frappe.utils import now_datetime


def fetch_daily_page_view_total_with_country():
    """Fetch real-time page view data by country and store it cumulatively for the current date."""
    
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

    # Build the Real-time API request (include both page path and country dimension)
    request = RunReportRequest(
    property=f"properties/{property_id}",
    dimensions=[Dimension(name="pagePath"), Dimension(name="country")],
    metrics=[Metric(name="screenPageViews")],  # Use screenPageViews instead of pageviews
    date_ranges=[DateRange(start_date="2023-01-01", end_date="today")]  # Set a specific date range
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

    # Process and store the data (page views per country)
    process_daily_response_total(response)


def process_daily_response_total(response):
    today_date = now_datetime().strftime('%Y-%m-%d')  # Store the data with date (no time)
    total_pageviews_by_page_and_country = {}

    # Aggregate page views by page and country
    for row in response.rows:
        page_path = row.dimension_values[0].value
        country = row.dimension_values[1].value
        pageviews = int(row.metric_values[0].value)  # Changed to pageviews

        if (page_path, country) in total_pageviews_by_page_and_country:
            total_pageviews_by_page_and_country[(page_path, country)] += pageviews
        else:
            total_pageviews_by_page_and_country[(page_path, country)] = pageviews

        frappe.logger().info(f"Page={page_path}, Country={country}, Pageviews={pageviews}")

    # Process and store the total page views per page and country for today
    for (page_path, country), total_pageviews in total_pageviews_by_page_and_country.items():
        # Check if record already exists for this page, country, and date
        existing_record = frappe.get_all('Visitor Page View', filters={
            'date': today_date,
            'page': page_path,
            'country': country
        }, fields=['name', 'views'])

        if existing_record:
            # Update existing record by adding new pageviews to existing count
            doc = frappe.get_doc('Visitor Page View', existing_record[0].name)
            doc.views += total_pageviews  # Add new pageviews to the existing total
            try:
                doc.save()
                frappe.logger().info(f"Updated existing Page View Total: {doc.name} with new views count")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Updating Page View Total")
        else:
            # Create new record
            doc = frappe.get_doc({
                'doctype': 'Visitor Page View',
                'page': page_path,
                'country': country,
                'views': total_pageviews,
                'date': today_date  # Store the date
            })
            try:
                doc.insert()
                frappe.logger().info(f"Inserted new Page View Total: {doc.name}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error Inserting Page View Total")

    frappe.db.commit()
