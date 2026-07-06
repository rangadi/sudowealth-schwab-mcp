import {
	KVTokenStore as SDKKVTokenStore,
	type TokenIdentifiers,
	type KVNamespace,
} from '@sudowealth/schwab-api'
import { TOKEN_KEY_PREFIX, TTL_31_DAYS } from './constants'
import { logger } from './log'

// Create a type that matches the existing interface
export interface KvTokenStore<T = any> {
	load(ids: TokenIdentifiers): Promise<T | null>
	save(ids: TokenIdentifiers, data: T): Promise<void>
	delete(ids: TokenIdentifiers): Promise<void>
	kvKey(ids: TokenIdentifiers): string
	migrate(fromIds: TokenIdentifiers, toIds: TokenIdentifiers): Promise<boolean>
	migrateIfNeeded(
		fromIds: TokenIdentifiers,
		toIds: TokenIdentifiers,
	): Promise<void>
}

/**
 * Creates a KV-backed token store using the SDK implementation
 * This maintains backward compatibility with the existing interface
 */
export function makeKvTokenStore<T = any>(kv: KVNamespace): KvTokenStore<T> {
	const sdkStore = new SDKKVTokenStore(kv, {
		keyPrefix: TOKEN_KEY_PREFIX,
		ttl: TTL_31_DAYS,
		autoMigrate: true,
	})

	return {
		load: async (ids: TokenIdentifiers) => {
			const result = await sdkStore.load(ids)
			return result as T | null
		},
		save: async (ids: TokenIdentifiers, data: T) => {
			await sdkStore.save(ids, data as any)
		},
		delete: async (ids: TokenIdentifiers) => {
			await sdkStore.delete(ids)
		},
		kvKey: (ids: TokenIdentifiers) => {
			return sdkStore.generateKey(ids)
		},
		migrate: async (fromIds: TokenIdentifiers, toIds: TokenIdentifiers) => {
			return sdkStore.migrate(fromIds, toIds)
		},
		migrateIfNeeded: async (
			fromIds: TokenIdentifiers,
			toIds: TokenIdentifiers,
		) => {
			const success = await sdkStore.migrate(fromIds, toIds)
			if (!success) {
				logger.warn('Token migration was not needed or failed', {
					from: sdkStore.generateKey(fromIds),
					to: sdkStore.generateKey(toIds),
				})
			}
		},
	}
}

// Re-export the type for backward compatibility
export type { TokenIdentifiers }
