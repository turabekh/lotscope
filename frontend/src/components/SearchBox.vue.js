import { ref } from 'vue';
import { api } from '@/lib/api';
const emit = defineEmits();
const query = ref('');
const results = ref([]);
const loading = ref(false);
let timer;
function onInput(value) {
    query.value = value == null ? '' : String(value);
    if (timer !== undefined)
        clearTimeout(timer);
    timer = setTimeout(() => {
        void runSearch();
    }, 250);
}
async function runSearch() {
    const term = query.value.trim();
    if (term === '') {
        results.value = [];
        return;
    }
    loading.value = true;
    try {
        const response = await api.search(term);
        results.value = response.results;
    }
    finally {
        loading.value = false;
    }
}
function choose(parcelNumber) {
    results.value = [];
    query.value = '';
    emit('select', parcelNumber);
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
const __VLS_0 = {}.QInput;
/** @type {[typeof __VLS_components.QInput, typeof __VLS_components.qInput, typeof __VLS_components.QInput, typeof __VLS_components.qInput, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.query),
    loading: (__VLS_ctx.loading),
    dense: true,
    outlined: true,
    placeholder: "Search address, owner, or parcel #",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.query),
    loading: (__VLS_ctx.loading),
    dense: true,
    outlined: true,
    placeholder: "Search address, owner, or parcel #",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    'onUpdate:modelValue': (__VLS_ctx.onInput)
};
__VLS_3.slots.default;
{
    const { prepend: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.QIcon;
    /** @type {[typeof __VLS_components.QIcon, typeof __VLS_components.qIcon, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        name: "search",
    }));
    const __VLS_10 = __VLS_9({
        name: "search",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
if (__VLS_ctx.results.length) {
    const __VLS_12 = {}.QList;
    /** @type {[typeof __VLS_components.QList, typeof __VLS_components.qList, typeof __VLS_components.QList, typeof __VLS_components.qList, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        bordered: true,
        ...{ class: "q-mt-xs bg-white" },
    }));
    const __VLS_14 = __VLS_13({
        bordered: true,
        ...{ class: "q-mt-xs bg-white" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.results))) {
        const __VLS_16 = {}.QItem;
        /** @type {[typeof __VLS_components.QItem, typeof __VLS_components.qItem, typeof __VLS_components.QItem, typeof __VLS_components.qItem, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            ...{ 'onClick': {} },
            key: (item.parcel_number),
            clickable: true,
        }));
        const __VLS_18 = __VLS_17({
            ...{ 'onClick': {} },
            key: (item.parcel_number),
            clickable: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        let __VLS_20;
        let __VLS_21;
        let __VLS_22;
        const __VLS_23 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.results.length))
                    return;
                __VLS_ctx.choose(item.parcel_number);
            }
        };
        __VLS_asFunctionalDirective(__VLS_directives.vRipple)(null, { ...__VLS_directiveBindingRestFields, }, null, null);
        __VLS_19.slots.default;
        const __VLS_24 = {}.QItemSection;
        /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
        const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
        __VLS_27.slots.default;
        const __VLS_28 = {}.QItemLabel;
        /** @type {[typeof __VLS_components.QItemLabel, typeof __VLS_components.qItemLabel, typeof __VLS_components.QItemLabel, typeof __VLS_components.qItemLabel, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
        const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
        __VLS_31.slots.default;
        (item.address ?? item.parcel_number);
        var __VLS_31;
        const __VLS_32 = {}.QItemLabel;
        /** @type {[typeof __VLS_components.QItemLabel, typeof __VLS_components.qItemLabel, typeof __VLS_components.QItemLabel, typeof __VLS_components.qItemLabel, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
            caption: true,
        }));
        const __VLS_34 = __VLS_33({
            caption: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        __VLS_35.slots.default;
        (item.owner ?? '—');
        (item.parcel_number);
        var __VLS_35;
        var __VLS_27;
        var __VLS_19;
    }
    var __VLS_15;
}
/** @type {__VLS_StyleScopedClasses['q-mt-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            query: query,
            results: results,
            loading: loading,
            onInput: onInput,
            choose: choose,
        };
    },
    __typeEmits: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
});
; /* PartiallyEnd: #4569/main.vue */
