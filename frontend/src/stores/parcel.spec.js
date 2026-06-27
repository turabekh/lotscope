import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from '@/lib/api';
import { useParcelStore } from '@/stores/parcel';
vi.mock('@/lib/api', async () => {
    const actual = await vi.importActual('@/lib/api');
    return {
        ApiError: actual.ApiError,
        api: {
            getParcel: vi.fn(),
            getVerdict: vi.fn(),
            refreshVerdict: vi.fn(),
        },
    };
});
const parcel = { parcel_number: '001', owner: 'Jane' };
const verdict = { parcel_number: '001', summary: 'RSA-5' };
beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
});
describe('parcel store', () => {
    it('select loads detail and verdict', async () => {
        vi.mocked(api.getParcel).mockResolvedValue(parcel);
        vi.mocked(api.getVerdict).mockResolvedValue(verdict);
        const store = useParcelStore();
        await store.select('001');
        expect(store.detail?.owner).toBe('Jane');
        expect(store.verdict?.summary).toBe('RSA-5');
        expect(store.error).toBeNull();
    });
    it('tolerates a missing verdict (404)', async () => {
        vi.mocked(api.getParcel).mockResolvedValue(parcel);
        vi.mocked(api.getVerdict).mockRejectedValue(new ApiError(404, 'no verdict'));
        const store = useParcelStore();
        await store.select('001');
        expect(store.detail?.parcel_number).toBe('001');
        expect(store.verdict).toBeNull();
    });
    it('records an error when the parcel fails to load', async () => {
        vi.mocked(api.getParcel).mockRejectedValue(new ApiError(500, 'boom'));
        const store = useParcelStore();
        await store.select('001');
        expect(store.detail).toBeNull();
        expect(store.error).toBe('boom');
    });
});
