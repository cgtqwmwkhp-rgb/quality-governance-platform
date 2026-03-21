export interface SubmissionField {
  label: string
  value: string
}

export interface SubmissionSection {
  title: string
  fields: SubmissionField[]
}

export type SubmissionSnapshot = Record<string, unknown>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readString(snapshot: SubmissionSnapshot | undefined, key: string): string | undefined {
  const value = snapshot?.[key]
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

function readArray(snapshot: SubmissionSnapshot | undefined, key: string): unknown[] {
  const value = snapshot?.[key]
  return Array.isArray(value) ? value : []
}

function readPhotoCount(snapshot: SubmissionSnapshot | undefined): number {
  const photos = snapshot?.photos
  if (isRecord(photos) && typeof photos.count === 'number') {
    return photos.count
  }
  return 0
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return 'Not provided'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || 'Not provided'
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return 'Not provided'
    return value.map((item) => stringifyValue(item)).join(', ')
  }
  if (isRecord(value)) {
    const entries = Object.entries(value)
      .filter(([, innerValue]) => innerValue !== null && innerValue !== undefined && innerValue !== '')
      .map(([innerKey, innerValue]) => `${innerKey}: ${stringifyValue(innerValue)}`)
    return entries.length > 0 ? entries.join(', ') : 'Not provided'
  }
  return String(value)
}

export function getSubmissionSnapshot(
  snapshot: Record<string, unknown> | null | undefined,
): SubmissionSnapshot | undefined {
  return snapshot && isRecord(snapshot) ? snapshot : undefined
}

export function formatSnapshotDateTime(date?: string, time?: string): string {
  if (!date && !time) return 'Not provided'
  if (date && time) return `${date} ${time}`
  return date || time || 'Not provided'
}

export function getSubmissionPhotoSummary(snapshot: SubmissionSnapshot | undefined): string {
  const photoCount = readPhotoCount(snapshot)
  return photoCount > 0 ? `${photoCount} uploaded` : 'No uploaded evidence'
}

export function buildIncidentSubmissionSections(
  snapshot: SubmissionSnapshot | undefined,
): SubmissionSection[] {
  if (!snapshot) return []

  return [
    {
      title: 'Reporter Intake',
      fields: [
        { label: 'Contract', value: stringifyValue(snapshot.contract) },
        { label: 'Other contract', value: stringifyValue(snapshot.contract_other) },
        { label: 'Was reporter involved', value: stringifyValue(snapshot.was_involved) },
        { label: 'Person name', value: stringifyValue(snapshot.person_name) },
        { label: 'Person role', value: stringifyValue(snapshot.person_role) },
        { label: 'Person contact', value: stringifyValue(snapshot.person_contact) },
      ],
    },
    {
      title: 'Event Details',
      fields: [
        { label: 'Location', value: stringifyValue(snapshot.location) },
        {
          label: 'Incident date/time',
          value: formatSnapshotDateTime(
            readString(snapshot, 'incident_date'),
            readString(snapshot, 'incident_time'),
          ),
        },
        { label: 'Description', value: stringifyValue(snapshot.description) },
        { label: 'Asset / vehicle', value: stringifyValue(snapshot.asset_number) },
      ],
    },
    {
      title: 'People, Harm, And Evidence',
      fields: [
        { label: 'Witnesses present', value: stringifyValue(snapshot.has_witnesses) },
        { label: 'Witness details', value: stringifyValue(snapshot.witness_names) },
        { label: 'Injuries reported', value: stringifyValue(snapshot.has_injuries) },
        { label: 'Injury detail', value: stringifyValue(snapshot.injuries) },
        { label: 'Medical assistance', value: stringifyValue(snapshot.medical_assistance) },
        { label: 'Evidence uploaded', value: getSubmissionPhotoSummary(snapshot) },
      ],
    },
  ]
}

export function buildComplaintSubmissionSections(
  snapshot: SubmissionSnapshot | undefined,
): SubmissionSection[] {
  if (!snapshot) return []

  return [
    {
      title: 'Reporter Intake',
      fields: [
        { label: 'Contract', value: stringifyValue(snapshot.contract) },
        { label: 'Other contract', value: stringifyValue(snapshot.contract_other) },
        { label: 'Complainant name', value: stringifyValue(snapshot.complainant_name) },
        { label: 'Complainant role', value: stringifyValue(snapshot.complainant_role) },
        { label: 'Complainant contact', value: stringifyValue(snapshot.complainant_contact) },
      ],
    },
    {
      title: 'Complaint Details',
      fields: [
        { label: 'Location / site', value: stringifyValue(snapshot.location) },
        { label: 'Description', value: stringifyValue(snapshot.description) },
        { label: 'Evidence uploaded', value: getSubmissionPhotoSummary(snapshot) },
      ],
    },
  ]
}

export function buildRtaSubmissionSections(
  snapshot: SubmissionSnapshot | undefined,
): SubmissionSection[] {
  if (!snapshot) return []

  const thirdParties = readArray(snapshot, 'third_parties')
  const thirdPartySummary =
    thirdParties.length > 0 ? thirdParties.map((party) => stringifyValue(party)).join(' | ') : 'Not provided'

  return [
    {
      title: 'Driver And Journey',
      fields: [
        { label: 'Employee name', value: stringifyValue(snapshot.employee_name) },
        { label: 'PE vehicle', value: stringifyValue(snapshot.pe_vehicle) },
        { label: 'Other vehicle registration', value: stringifyValue(snapshot.pe_vehicle_other) },
        { label: 'Passengers present', value: stringifyValue(snapshot.has_passengers) },
        { label: 'Passenger details', value: stringifyValue(snapshot.passenger_details) },
        { label: 'Purpose of journey', value: stringifyValue(snapshot.purpose_of_journey) },
      ],
    },
    {
      title: 'Collision Details',
      fields: [
        { label: 'Location', value: stringifyValue(snapshot.location) },
        {
          label: 'Accident date/time',
          value: formatSnapshotDateTime(
            readString(snapshot, 'accident_date'),
            readString(snapshot, 'accident_time'),
          ),
        },
        { label: 'Accident type', value: stringifyValue(snapshot.accident_type) },
        { label: 'Vehicle count', value: stringifyValue(snapshot.vehicle_count) },
        { label: 'Impact point', value: stringifyValue(snapshot.impact_point) },
        { label: 'Damage description', value: stringifyValue(snapshot.damage_description) },
        { label: 'Drivable', value: stringifyValue(snapshot.is_drivable) },
        { label: 'Speed', value: stringifyValue(snapshot.speed) },
      ],
    },
    {
      title: 'Scene And Evidence',
      fields: [
        { label: 'Weather', value: stringifyValue(snapshot.weather) },
        { label: 'Road condition', value: stringifyValue(snapshot.road_condition) },
        { label: 'Witnesses present', value: stringifyValue(snapshot.has_witnesses) },
        { label: 'Witness details', value: stringifyValue(snapshot.witness_details) },
        { label: 'Emergency services', value: stringifyValue(snapshot.emergency_services) },
        { label: 'Police reference', value: stringifyValue(snapshot.police_ref) },
        { label: 'Dashcam available', value: stringifyValue(snapshot.has_dashcam) },
        { label: 'CCTV available', value: stringifyValue(snapshot.has_cctv) },
        { label: 'Third parties', value: thirdPartySummary },
        { label: 'Evidence uploaded', value: getSubmissionPhotoSummary(snapshot) },
      ],
    },
  ]
}
