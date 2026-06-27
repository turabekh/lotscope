import { defineStore } from 'pinia';
import { ref } from 'vue';
import { ApiError, api } from '@/lib/api';
export const useParcelStore = defineStore('parcel', () => {
    const detail = ref(null);
    const verdict = ref(null);
    const loading = ref(false);
    const error = ref(null);
    async function select(parcelNumber) {
        loading.value = true;
        error.value = null;
        verdict.value = null;
        try {
            detail.value = await api.getParcel(parcelNumber);
            verdict.value = await loadVerdict(parcelNumber);
        }
        catch (cause) {
            detail.value = null;
            error.value = cause instanceof Error ? cause.message : 'Failed to load parcel.';
        }
        finally {
            loading.value = false;
        }
    }
    async function loadVerdict(parcelNumber) {
        try {
            return await api.getVerdict(parcelNumber);
        }
        catch (cause) {
            if (cause instanceof ApiError && cause.status === 404)
                return null;
            throw cause;
        }
    }
    async function refreshVerdict() {
        if (detail.value === null)
            return;
        verdict.value = await api.refreshVerdict(detail.value.parcel_number);
    }
    function clear() {
        detail.value = null;
        verdict.value = null;
        error.value = null;
    }
    return { detail, verdict, loading, error, select, refreshVerdict, clear };
});
