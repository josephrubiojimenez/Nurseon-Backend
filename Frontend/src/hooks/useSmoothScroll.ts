export function useSmoothScroll() {
    const scrollToElement = (elementId: string, offset: number = 80) => {
        const element = document.getElementById(elementId);
        if (!element) {
            console.warn(`Element with ID ${elementId} not found`);
            return;
        }

        const topPosition = element.getBoundingClientRect().top + window.scrollY - offset;
        
        window.scrollTo({
            top: topPosition,
            behavior: 'smooth'
        });
    };

    return { scrollToElement };
}