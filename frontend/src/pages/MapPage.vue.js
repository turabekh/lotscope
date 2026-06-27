import ParcelPanel from '@/components/ParcelPanel.vue';
import SearchBox from '@/components/SearchBox.vue';
import { useParcelStore } from '@/stores/parcel';
const store = useParcelStore();
function onSelect(parcelNumber) {
    void store.select(parcelNumber);
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
const __VLS_0 = {}.QLayout;
/** @type {[typeof __VLS_components.QLayout, typeof __VLS_components.qLayout, typeof __VLS_components.QLayout, typeof __VLS_components.qLayout, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    view: "hHh Lpr fFf",
}));
const __VLS_2 = __VLS_1({
    view: "hHh Lpr fFf",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_4 = {};
__VLS_3.slots.default;
const __VLS_5 = {}.QHeader;
/** @type {[typeof __VLS_components.QHeader, typeof __VLS_components.qHeader, typeof __VLS_components.QHeader, typeof __VLS_components.qHeader, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(__VLS_5, new __VLS_5({
    elevated: true,
    ...{ class: "bg-primary text-white" },
}));
const __VLS_7 = __VLS_6({
    elevated: true,
    ...{ class: "bg-primary text-white" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_8.slots.default;
const __VLS_9 = {}.QToolbar;
/** @type {[typeof __VLS_components.QToolbar, typeof __VLS_components.qToolbar, typeof __VLS_components.QToolbar, typeof __VLS_components.qToolbar, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({}));
const __VLS_11 = __VLS_10({}, ...__VLS_functionalComponentArgsRest(__VLS_10));
__VLS_12.slots.default;
const __VLS_13 = {}.QToolbarTitle;
/** @type {[typeof __VLS_components.QToolbarTitle, typeof __VLS_components.qToolbarTitle, typeof __VLS_components.QToolbarTitle, typeof __VLS_components.qToolbarTitle, ]} */ ;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent(__VLS_13, new __VLS_13({}));
const __VLS_15 = __VLS_14({}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_16.slots.default;
var __VLS_16;
var __VLS_12;
var __VLS_8;
const __VLS_17 = {}.QDrawer;
/** @type {[typeof __VLS_components.QDrawer, typeof __VLS_components.qDrawer, typeof __VLS_components.QDrawer, typeof __VLS_components.qDrawer, ]} */ ;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
    width: (400),
    showIfAbove: true,
    bordered: true,
    side: "left",
}));
const __VLS_19 = __VLS_18({
    width: (400),
    showIfAbove: true,
    bordered: true,
    side: "left",
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
__VLS_20.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "q-pa-md" },
});
/** @type {[typeof SearchBox, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(SearchBox, new SearchBox({
    ...{ 'onSelect': {} },
}));
const __VLS_22 = __VLS_21({
    ...{ 'onSelect': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onSelect: (__VLS_ctx.onSelect)
};
var __VLS_23;
const __VLS_28 = {}.QSeparator;
/** @type {[typeof __VLS_components.QSeparator, typeof __VLS_components.qSeparator, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
/** @type {[typeof ParcelPanel, ]} */ ;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent(ParcelPanel, new ParcelPanel({}));
const __VLS_33 = __VLS_32({}, ...__VLS_functionalComponentArgsRest(__VLS_32));
var __VLS_20;
const __VLS_35 = {}.QPageContainer;
/** @type {[typeof __VLS_components.QPageContainer, typeof __VLS_components.qPageContainer, typeof __VLS_components.QPageContainer, typeof __VLS_components.qPageContainer, ]} */ ;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent(__VLS_35, new __VLS_35({}));
const __VLS_37 = __VLS_36({}, ...__VLS_functionalComponentArgsRest(__VLS_36));
__VLS_38.slots.default;
const __VLS_39 = {}.QPage;
/** @type {[typeof __VLS_components.QPage, typeof __VLS_components.qPage, typeof __VLS_components.QPage, typeof __VLS_components.qPage, ]} */ ;
// @ts-ignore
const __VLS_40 = __VLS_asFunctionalComponent(__VLS_39, new __VLS_39({
    ...{ class: "flex flex-center text-grey" },
}));
const __VLS_41 = __VLS_40({
    ...{ class: "flex flex-center text-grey" },
}, ...__VLS_functionalComponentArgsRest(__VLS_40));
__VLS_42.slots.default;
var __VLS_42;
var __VLS_38;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['bg-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['q-pa-md']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ParcelPanel: ParcelPanel,
            SearchBox: SearchBox,
            onSelect: onSelect,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
