import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from '@/lib/api';
function mockFetch(status, body) {
    return vi.fn().mockResolvedValue({
        ok: status >= 200 && status < 300,
        status,
        statusText: 'status',
        json: () => Promise.resolve(body),
    });
}
afterEach(() => {
    vi.unstubAllGlobals();
});
describe('api', () => {
    it('search calls the search endpoint and returns the body', async () => {
        const fetchMock = mockFetch(200, { query: 'main', results: [] });
        vi.stubGlobal('fetch', fetchMock);
        const result = await api.search('main st');
        expect(result.query).toBe('main');
        expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/search?q=main%20st&limit=10'), expect.anything());
    });
    it('ask posts the question', async () => {
        const fetchMock = mockFetch(200, {
            answer: 'Yes',
            citations: [{ source: 'Title 14', section: '14-701' }],
            confidence: 'high',
            is_informational: true,
        });
        vi.stubGlobal('fetch', fetchMock);
        const answer = await api.ask('001', 'Can I build?');
        expect(answer.citations[0]?.section).toBe('14-701');
        expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/parcels/001/ask'), expect.objectContaining({ method: 'POST' }));
    });
    it('throws ApiError with the detail on a failure response', async () => {
        vi.stubGlobal('fetch', mockFetch(404, { detail: 'Parcel not found.' }));
        await expect(api.getParcel('missing')).rejects.toMatchObject({
            status: 404,
            message: 'Parcel not found.',
        });
        await expect(api.getParcel('missing')).rejects.toBeInstanceOf(ApiError);
    });
});
