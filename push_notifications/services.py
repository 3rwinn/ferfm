from exponent_server_sdk import (PushClient, PushMessage, PushServerError, PushTicketError, DeviceNotRegisteredError)
from requests.exceptions import ConnectionError, HTTPError

from django.conf import settings
from .models import ExpoPushToken, Notification, NotificationDelivery
from django.utils import timezone
import logging
from .tasks import queue_notification_for_sending

logger = logging.getLogger(__name__)

def send_expo_push_messages(notification_id):
    """
    Sends a given notification to all active ExpoPushToken recipients.
    Handles creation of NotificationDelivery records and updates their status based on Expo's response.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        logger.error(f"Notification with id {notification_id} not found. Cannot send.")
        return

    active_tokens = ExpoPushToken.objects.filter(is_active=True)
    if not active_tokens:
        logger.info(f"No active Expo push tokens found for notification {notification.id} ('{notification.title}').")
        notification.status = 'failed' # Or a new status like 'no_recipients'
        notification.sent_at = timezone.now()
        notification.save()
        return

    messages_to_send = []
    delivery_records_map = {} # To map token string to delivery record for status updates

    notification.status = 'sending'
    notification.sent_at = timezone.now()
    notification.save()

    for expo_token_obj in active_tokens:
        # Create or get delivery record
        delivery, created = NotificationDelivery.objects.get_or_create(
            notification=notification,
            expo_push_token=expo_token_obj,
            defaults={'status': 'pending_send'} # Should be pending_send initially
        )
        # Ensure status is ready for sending if record already existed but failed previously
        if not created and delivery.status not in ['receipt_ok']:
             delivery.status = 'pending_send' 
             # Reset other fields if re-sending the same notification after a failure on this delivery
             delivery.push_ticket_id = None
             delivery.receipt_checked_at = None
             delivery.receipt_status_text = None
             delivery.receipt_details = None
             delivery.save()
        
        messages_to_send.append(
            PushMessage(
                to=expo_token_obj.token,
                title=notification.title,
                body=notification.body,
                data=notification.data or {},
                sound="default", # You can customize this
                # extra fields like badge, ttl, etc. can be added here
            )
        )
        delivery_records_map[expo_token_obj.token] = delivery

    logger.info(f"Attempting to send notification '{notification.title}' to {len(messages_to_send)} tokens.")

    try:
        # Send messages in chunks if necessary (Expo recommends chunks of up to 100)
        client = PushClient()
        # The send_messages method automatically chunks
        push_tickets = client.publish_multiple(messages_to_send)
        
        all_tickets_successful = True
        for idx, ticket in enumerate(push_tickets):
            token_str = messages_to_send[idx].to # Get original token string
            delivery_record = delivery_records_map.get(token_str)
            if not delivery_record:
                logger.error(f"Could not find delivery record for token {token_str} during ticket processing.")
                continue

            if ticket.status == 'ok':
                delivery_record.push_ticket_id = ticket.id
                delivery_record.status = 'sent_to_expo' # Or 'receipt_pending_check' if you prefer
                logger.info(f"Successfully sent to Expo for token {token_str}, ticket ID: {ticket.id}")
            else:
                all_tickets_successful = False
                delivery_record.status = 'expo_error'
                error_details = {
                    'message': ticket.message, 
                    'details': ticket.details
                }
                if ticket.is_device_not_registered(): # Specific check for DeviceNotRegistered
                     error_details['error_type'] = 'DeviceNotRegistered'
                     # Optionally deactivate token here, or wait for receipt check for consistency
                     # expo_token_obj = delivery_record.expo_push_token
                     # expo_token_obj.is_active = False
                     # expo_token_obj.save()
                     # logger.info(f"Token {expo_token_obj.token} marked inactive due to DeviceNotRegistered at send time.")
                delivery_record.receipt_details = error_details # Store error from ticket
                logger.error(f"Expo send error for token {token_str}: {ticket.message} - Details: {ticket.details}")
            delivery_record.save()

        if all_tickets_successful:
            notification.status = 'sent' # All sent to Expo, awaiting receipts
        else:
            notification.status = 'completed_with_errors' # Or a more granular status
        notification.save()
        logger.info(f"Notification '{notification.title}' processing complete. Status: {notification.status}")

    except PushServerError as e:
        logger.error(f"Expo PushServerError for notification '{notification.title}': {e}")
        notification.status = 'failed'
        notification.save()
        # Potentially mark all deliveries as errored for this notification
        NotificationDelivery.objects.filter(notification=notification, status='pending_send').update(status='expo_error', receipt_details={"error": "PushServerError", "details": str(e)})
    except (ConnectionError, HTTPError) as e:
        logger.error(f"Network error sending notification '{notification.title}': {e}")
        notification.status = 'failed' # Or 'queued' for retry, depending on strategy
        notification.save()
        NotificationDelivery.objects.filter(notification=notification, status='pending_send').update(status='expo_error', receipt_details={"error": "NetworkError", "details": str(e)})
    except Exception as e:
        logger.exception(f"Unexpected error sending notification '{notification.title}': {e}")
        notification.status = 'failed'
        notification.save()
        NotificationDelivery.objects.filter(notification=notification, status='pending_send').update(status='expo_error', receipt_details={"error": "UnexpectedError", "details": str(e)})


def check_expo_push_receipts(delivery_ids_batch):
    """
    Checks receipts for a batch of NotificationDelivery IDs.
    Updates NotificationDelivery records and deactivates tokens if DeviceNotRegistered.
    """
    deliveries_to_check = NotificationDelivery.objects.filter(
        id__in=delivery_ids_batch,
        push_ticket_id__isnull=False, 
        # status='sent_to_expo' # Or 'receipt_pending_check'
    ).exclude(status__in=['receipt_ok', 'receipt_error']) # Avoid re-checking already processed
    
    if not deliveries_to_check:
        logger.info("No deliveries in the batch require receipt checking.")
        return

    ticket_ids = [d.push_ticket_id for d in deliveries_to_check if d.push_ticket_id]
    if not ticket_ids:
        logger.info("No push ticket IDs found in the batch to check receipts for.")
        # Potentially mark these as errored if they were expected to have tickets
        for delivery in deliveries_to_check:
            if not delivery.push_ticket_id and delivery.status not in ['expo_error', 'receipt_error']:
                delivery.status = 'expo_error' # Or a new status like 'missing_ticket'
                delivery.receipt_details = {"error": "MissingPushTicketID"}
                delivery.receipt_checked_at = timezone.now()
                delivery.save()
        return

    logger.info(f"Checking receipts for {len(ticket_ids)} tickets.")
    try:
        client = PushClient()
        # The get_receipts method automatically chunks
        receipts = client.get_receipts(ticket_ids)

        processed_notification_ids = set()

        for ticket_id, receipt in receipts.items():
            try:
                delivery = NotificationDelivery.objects.get(push_ticket_id=ticket_id)
                delivery.receipt_checked_at = timezone.now()
                delivery.receipt_details = receipt.details # Store full receipt details
                processed_notification_ids.add(delivery.notification_id)

                if receipt.status == 'ok':
                    delivery.status = 'receipt_ok'
                    delivery.receipt_status_text = 'ok'
                    logger.info(f"Receipt OK for ticket ID: {ticket_id}")
                else: # Error case
                    delivery.status = 'receipt_error'
                    delivery.receipt_status_text = receipt.details.get('error', 'unknown_error') if receipt.details else 'unknown_error'
                    logger.warning(f"Receipt error for ticket ID {ticket_id}: {receipt.message} - Details: {receipt.details}")
                    
                    if receipt.details and receipt.details.get('error') == 'DeviceNotRegistered':
                        expo_token_obj = delivery.expo_push_token
                        if expo_token_obj.is_active:
                            expo_token_obj.is_active = False
                            expo_token_obj.save()
                            logger.info(f"Token {expo_token_obj.token} marked inactive due to DeviceNotRegistered receipt.")
                delivery.save()

            except NotificationDelivery.DoesNotExist:
                logger.error(f"NotificationDelivery not found for ticket_id {ticket_id} during receipt check.")
            except Exception as e:
                logger.exception(f"Error processing receipt for ticket_id {ticket_id}: {e}")
        
        # After processing receipts, update overall Notification statuses
        # This is an approximation; a more robust way might be needed if notifications span many batches
        for notif_id in processed_notification_ids:
            update_overall_notification_status(notif_id)

    except PushServerError as e:
        logger.error(f"PushServerError while getting receipts: {e}")
        # Decide how to mark these deliveries - e.g., keep as pending or mark as error
    except (ConnectionError, HTTPError) as e:
        logger.error(f"Network error while getting receipts: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error while getting receipts: {e}")

def update_overall_notification_status(notification_id):
    """
    Updates the parent Notification status based on its delivery statuses.
    Call this after a batch of receipts has been processed for a notification.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        deliveries = notification.deliveries.all()
        total_deliveries = deliveries.count()

        if total_deliveries == 0 and notification.status not in ['draft', 'scheduled', 'failed']:
            # This might happen if tokens were deactivated between send and receipt check
            # or if send_expo_push_messages failed to create deliveries
            logger.info(f"Notification {notification.id} has no deliveries, marking as failed or check logic.")
            # notification.status = 'failed' # Or some other appropriate status
            # notification.save()
            return
        
        if total_deliveries == 0 and notification.status in ['draft', 'scheduled']:
            return # No deliveries yet, so status remains as is

        # Check if all deliveries are processed (i.e., not pending_send, sent_to_expo, receipt_pending_check)
        pending_statuses = ['pending_send', 'sent_to_expo', 'receipt_pending_check']
        is_fully_processed = not deliveries.filter(status__in=pending_statuses).exists()

        if is_fully_processed:
            successful_deliveries = deliveries.filter(status='receipt_ok').count()
            if successful_deliveries == total_deliveries:
                notification.status = 'completed_success'
            else:
                notification.status = 'completed_with_errors'
            logger.info(f"Notification {notification.id} fully processed. New status: {notification.status}")
            notification.save()
        # Else: Notification is still partially being processed or awaiting more receipts, status remains 'sent' or 'completed_with_errors' from send phase

    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found for status update.")
    except Exception as e:
        logger.exception(f"Error updating overall status for notification {notification_id}: {e}")

def create_and_queue_actu_notification_service(actu_instance):
    """
    Creates a Notification from an Actu instance and queues it for sending.
    """
    logger.info(f"Actu object created/updated: ID {actu_instance.id}. Preparing notification.")
    
    # Customize title and body as needed
    title = f"Nouvelle Actualité : {actu_instance.text[:50]}..." if len(actu_instance.text) > 50 else f"Nouvelle Actualité : {actu_instance.text}"
    body = actu_instance.text
    # You could add more specific data from 'actu_instance' to the 'data' field if the client app can use it
    # e.g., data = {"actu_id": actu_instance.id, "type": "new_actu"}
    data = {"actu_id": actu_instance.id, "type": "new_actu"} 

    try:
        notification = Notification.objects.create(
            title=title,
            body=body,
            data=data,
            # creator can be null if system-generated
            # status will be set to 'queued' or 'scheduled' by queue_notification_for_sending
        )
        logger.info(f"Notification object ID {notification.id} created for Actu ID {actu_instance.id}.")
        
        # Queue it for sending (this will set status to 'queued')
        # If you wanted to allow scheduling for these, logic would need to be added here
        # or rely on admins to change status to draft and schedule manually.
        # For automatic, direct queuing is common.
        queue_notification_for_sending(notification.id) # This sets status to 'queued'
        
        logger.info(f"Notification ID {notification.id} for Actu ID {actu_instance.id} has been queued for sending.")
        
    except Exception as e:
        logger.exception(f"Error creating or queuing notification for Actu ID {actu_instance.id}: {e}") 