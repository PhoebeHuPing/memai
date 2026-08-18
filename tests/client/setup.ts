// Mock scrollIntoView which is not implemented in jsdom
Element.prototype.scrollIntoView = () => {}
