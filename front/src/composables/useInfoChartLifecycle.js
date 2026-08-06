export function useInfoChartLifecycle() {
  let containerObserver = null;

  const resizeVisibleChartContainers = ({ deviceChartRef, stationChartRef, popChartRef }) => {
    if (deviceChartRef?.value) {
      deviceChartRef.value.style.visibility = 'visible';
      deviceChartRef.value.style.height = '400px';
      deviceChartRef.value.style.display = 'block';
      deviceChartRef.value.style.width = '100%';
    }

    if (stationChartRef?.value) {
      stationChartRef.value.style.visibility = 'visible';
      stationChartRef.value.style.height = '400px';
      stationChartRef.value.style.display = 'block';
      stationChartRef.value.style.width = '100%';
    }

    if (popChartRef?.value) {
      popChartRef.value.style.visibility = 'visible';
      popChartRef.value.style.height = '400px';
      popChartRef.value.style.display = 'block';
      popChartRef.value.style.width = '100%';
    }
  };

  const disposeChartInstances = (charts = []) => {
    charts.forEach((chart) => {
      if (chart && typeof chart.dispose === 'function') {
        chart.dispose();
      }
    });
  };

  const observeContainerVisibility = ({ containerRef, onVisible, threshold = 0.1 }) => {
    if (!containerRef?.value) return;

    containerObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && entry.intersectionRatio > 0) {
          onVisible?.();
        }
      });
    }, { threshold });

    containerObserver.observe(containerRef.value);
  };

  const cleanupContainerObserver = () => {
    if (containerObserver) {
      containerObserver.disconnect();
      containerObserver = null;
    }
  };

  return {
    resizeVisibleChartContainers,
    disposeChartInstances,
    observeContainerVisibility,
    cleanupContainerObserver,
  };
}
