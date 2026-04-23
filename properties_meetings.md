# Properties Meeting

In the properties object, you can include the following fields:


| Field                       | Description                                                                                                                                                                                                                       |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hs_timestamp`              | Required. This field marks the date and time that the meeting occurred. You can use either a Unix timestamp in milliseconds or UTC format. When the property value is missing, the value will default to `hs_meeting_start_time.` |
| `hs_meeting_title`          | The title of the meeting.                                                                                                                                                                                                         |
| `hubspot_owner_id`          | The [ID of the owner](/docs/api-reference/latest/crm/owners/guide) associated with the meeting. This field determines the user listed as the meeting creator on the record timeline.                                              |
| `hs_meeting_body`           | The meeting description.                                                                                                                                                                                                          |
| `hs_internal_meeting_notes` | The internal notes you take for your team during a meeting that are not included in the attendee meeting description.                                                                                                             |
| `hs_meeting_external_url`   | The external URL for the calendar event. For example, this could be a Google calendar link or a Microsoft Outlook calendar link.                                                                                                  |
| `hs_meeting_location`       | Where the meeting takes place. The value could be a physical address, a conference room, a videoconference link, or a phone number. This appears on the calendar invite on the attendee’s calendar.                               |
| `hs_meeting_start_time`     | The date and time when the meeting starts. The value for this property should match the value for `hs_timestamp`.                                                                                                                 |
| `hs_meeting_end_time`       | The date and time when the meeting ends.                                                                                                                                                                                          |
| `hs_meeting_outcome`        | The outcome of the meeting. The outcome values are scheduled, completed, rescheduled, no show, and canceled.                                                                                                                      |
| `hs_activity_type`          | The type of meeting. The options are based on the [meeting types set in your HubSpot account.](https://knowledge.hubspot.com/meetings-tool/how-do-i-create-and-use-call-and-meeting-types)                                        |
| `hs_attachment_ids`         | The IDs of the meeting’s attachments. Multiple attachment IDs are separated by a semi-colon.                                                                                                                                      |


## Associate existing meetings with lead

To associate a meeting with records, such as a contact and its associated companies, make a PUT request to /crm/objects/2026-03/meetings/{meetingId}/associations/lead/{toObjectId}/601. The request URL contains the following fields:


| Field        | Description                                                       |
| ------------ | ----------------------------------------------------------------- |
| `meetingId`  | The ID of the meeting.                                            |
| `toObjectId` | The ID of the record that you want to associate the meeting with. |


