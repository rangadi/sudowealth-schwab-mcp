import { type ValidatedEnv } from '../../types/env'
import { ALLOWLIST_KEY_PREFIX, INVITE_KEY_PREFIX } from '../shared/constants'
import { logger } from '../shared/log'

type KV = ValidatedEnv['OAUTH_KV']

const allowlistLogger = logger.child('allowlist')

/**
 * Invite codes are used verbatim in KV keys, so constrain them to a safe
 * charset. Anything else is treated as "no code provided".
 */
const INVITE_CODE_PATTERN = /^[A-Za-z0-9_-]{8,64}$/

export function normalizeInviteCode(raw: unknown): string | undefined {
	if (typeof raw !== 'string') return undefined
	const trimmed = raw.trim()
	return INVITE_CODE_PATTERN.test(trimmed) ? trimmed : undefined
}

/**
 * Checks whether a Schwab customer has been enrolled.
 * Enrollment records live at `allowed:<schwabClientCustomerId>`.
 */
export async function isCustomerAllowed(
	kv: KV,
	schwabCustomerId: string,
): Promise<boolean> {
	const value = await kv.get(`${ALLOWLIST_KEY_PREFIX}${schwabCustomerId}`)
	return value !== null
}

/**
 * Redeems a one-time invite code (`invite:<code>`) and enrolls the customer.
 * The invite is deleted on success so a leaked code can't be reused.
 *
 * @returns true if the code was valid and the customer is now enrolled
 */
export async function enrollWithInviteCode(
	kv: KV,
	inviteCode: string,
	schwabCustomerId: string,
): Promise<boolean> {
	const inviteKey = `${INVITE_KEY_PREFIX}${inviteCode}`
	const invite = await kv.get(inviteKey)
	if (invite === null) {
		allowlistLogger.warn('Invalid or already-used invite code presented', {
			inviteCode,
		})
		return false
	}

	let inviteNote: string | undefined
	try {
		inviteNote = (JSON.parse(invite) as { note?: string }).note
	} catch {
		// Invite value is free-form; a note is optional.
	}

	await kv.put(
		`${ALLOWLIST_KEY_PREFIX}${schwabCustomerId}`,
		JSON.stringify({
			enrolledAt: new Date().toISOString(),
			...(inviteNote ? { note: inviteNote } : {}),
		}),
	)
	await kv.delete(inviteKey)
	// customerIdPrefix: full customer IDs are redacted from logs by design
	allowlistLogger.info('Updated allowlist with newly enrolled customer', {
		inviteCode,
		customerIdPrefix: `${schwabCustomerId.slice(0, 8)}...`,
		...(inviteNote ? { note: inviteNote } : {}),
	})
	return true
}
