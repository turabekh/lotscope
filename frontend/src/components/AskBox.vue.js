import { ref } from 'vue';
import { ApiError, api } from '@/lib/api';
const props = defineProps();
const question = ref('');
const answer = ref(null);
const loading = ref(false);
const error = ref(null);
async function ask() {
    const text = question.value.trim();
    if (text === '')
        return;
    loading.value = true;
    error.value = null;
    try {
        answer.value = await api.ask(props.parcelNumber, text);
    }
    catch (cause) {
        answer.value = null;
        error.value = cause instanceof ApiError ? cause.message : 'Failed to get an answer.';
    }
    finally {
        loading.value = false;
    }
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
const __VLS_0 = {}.QCard;
/** @type {[typeof __VLS_components.QCard, typeof __VLS_components.qCard, typeof __VLS_components.QCard, typeof __VLS_components.qCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    flat: true,
    bordered: true,
}));
const __VLS_2 = __VLS_1({
    flat: true,
    bordered: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_4 = {};
__VLS_3.slots.default;
const __VLS_5 = {}.QCardSection;
/** @type {[typeof __VLS_components.QCardSection, typeof __VLS_components.qCardSection, typeof __VLS_components.QCardSection, typeof __VLS_components.qCardSection, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(__VLS_5, new __VLS_5({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_8.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-subtitle1 q-mb-sm" },
});
const __VLS_9 = {}.QInput;
/** @type {[typeof __VLS_components.QInput, typeof __VLS_components.qInput, typeof __VLS_components.QInput, typeof __VLS_components.qInput, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.question),
    dense: true,
    outlined: true,
    placeholder: "Can I build a duplex here?",
}));
const __VLS_11 = __VLS_10({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.question),
    dense: true,
    outlined: true,
    placeholder: "Can I build a duplex here?",
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
let __VLS_13;
let __VLS_14;
let __VLS_15;
const __VLS_16 = {
    onKeyup: (__VLS_ctx.ask)
};
__VLS_12.slots.default;
{
    const { after: __VLS_thisSlot } = __VLS_12.slots;
    const __VLS_17 = {}.QBtn;
    /** @type {[typeof __VLS_components.QBtn, typeof __VLS_components.qBtn, ]} */ ;
    // @ts-ignore
    const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
        ...{ 'onClick': {} },
        round: true,
        dense: true,
        icon: "send",
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_19 = __VLS_18({
        ...{ 'onClick': {} },
        round: true,
        dense: true,
        icon: "send",
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_18));
    let __VLS_21;
    let __VLS_22;
    let __VLS_23;
    const __VLS_24 = {
        onClick: (__VLS_ctx.ask)
    };
    var __VLS_20;
}
var __VLS_12;
if (__VLS_ctx.error) {
    const __VLS_25 = {}.QBanner;
    /** @type {[typeof __VLS_components.QBanner, typeof __VLS_components.qBanner, typeof __VLS_components.QBanner, typeof __VLS_components.qBanner, ]} */ ;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({
        dense: true,
        ...{ class: "bg-red-1 text-negative q-mt-sm" },
    }));
    const __VLS_27 = __VLS_26({
        dense: true,
        ...{ class: "bg-red-1 text-negative q-mt-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
    __VLS_28.slots.default;
    (__VLS_ctx.error);
    var __VLS_28;
}
if (__VLS_ctx.answer) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "q-mt-md" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-body2" },
    });
    (__VLS_ctx.answer.answer);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-caption text-grey q-mt-sm" },
    });
    (__VLS_ctx.answer.confidence);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "q-gutter-xs q-mt-xs" },
    });
    for (const [citation, index] of __VLS_getVForSourceType((__VLS_ctx.answer.citations))) {
        const __VLS_29 = {}.QChip;
        /** @type {[typeof __VLS_components.QChip, typeof __VLS_components.qChip, ]} */ ;
        // @ts-ignore
        const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({
            key: (index),
            dense: true,
            outline: true,
            label: (`${citation.source} ${citation.section}`),
        }));
        const __VLS_31 = __VLS_30({
            key: (index),
            dense: true,
            outline: true,
            label: (`${citation.source} ${citation.section}`),
        }, ...__VLS_functionalComponentArgsRest(__VLS_30));
    }
}
var __VLS_8;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['text-subtitle1']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mb-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-negative']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mt-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mt-md']} */ ;
/** @type {__VLS_StyleScopedClasses['text-body2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mt-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['q-gutter-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mt-xs']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            question: question,
            answer: answer,
            loading: loading,
            error: error,
            ask: ask,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
