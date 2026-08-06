export function useInfoTerminalCharts(deps) {
  const {
    echarts,
    deviceChartRef,
    stationChartRef,
    popChartRef,
    countryStats,
    totalDevices,
    stationCountByCountry,
    popCountByCountry,
    getChineseCountryName,
    getPopCountryChineseName,
    maxRetryCount = 5,
  } = deps;

  let deviceChart = null;
  let stationChart = null;
  let popChart = null;

  let deviceChartRetryCount = 0;
  let stationChartRetryCount = 0;
  let popChartRetryCount = 0;

  let deviceChartRetryTimer = null;
  let stationChartRetryTimer = null;
  let popChartRetryTimer = null;

  const resetTerminalChartRetries = () => {
    deviceChartRetryCount = 0;
    stationChartRetryCount = 0;
    popChartRetryCount = 0;
  };

  const disposeTerminalCharts = () => {
    // 组件卸载后停止重试链，清理未触发的重试定时器
    [deviceChartRetryTimer, stationChartRetryTimer, popChartRetryTimer].forEach((timer) => {
      if (timer) clearTimeout(timer);
    });
    deviceChartRetryTimer = null;
    stationChartRetryTimer = null;
    popChartRetryTimer = null;
    if (deviceChart) {
      deviceChart.dispose();
      deviceChart = null;
    }
    if (stationChart) {
      stationChart.dispose();
      stationChart = null;
    }
    if (popChart) {
      popChart.dispose();
      popChart = null;
    }
  };

  const resizeTerminalCharts = () => {
    if (deviceChart) deviceChart.resize();
    if (stationChart) stationChart.resize();
    if (popChart) popChart.resize();
  };

  const updateDeviceChart = () => {
    if (!deviceChart) {
      initDeviceChart();
      return;
    }

    const countryData = Object.entries(countryStats.value)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    const countries = countryData.map((item) => item[0].split('/')[0]);
    const deviceCounts = countryData.map((item) => item[1]);
    const percentages = deviceCounts.map((count) => parseFloat(((count / totalDevices.value) * 100).toFixed(2)));

    const colors = ['#5470C6', '#EE6666'];
    const option = {
      color: colors,
      title: {
        text: '国家设备分布 (Top 10)',
        left: 'center',
        textStyle: { color: '#333' },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter(params) {
          let result = `${params[0].name}<br/>`;
          params.forEach((param) => {
            const marker = `<span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:${param.color};"></span>`;
            if (param.seriesName === '设备数量') {
              result += `${marker}${param.seriesName}: ${param.value.toLocaleString()} 台<br/>`;
            } else {
              result += `${marker}${param.seriesName}: ${param.value}%<br/>`;
            }
          });
          return result;
        },
      },
      grid: {
        left: '3%',
        right: '12%',
        bottom: '3%',
        containLabel: true,
      },
      legend: {
        data: ['设备数量', '百分占比'],
        top: 30,
      },
      xAxis: [
        {
          type: 'category',
          axisTick: { alignWithLabel: true },
          data: countries,
          axisLabel: { interval: 0, rotate: 30 },
        },
      ],
      yAxis: [
        {
          type: 'value',
          name: '设备数量',
          position: 'left',
          axisLine: { show: true, lineStyle: { color: colors[0] } },
          axisLabel: { formatter: '{value} 台' },
        },
        {
          type: 'value',
          name: '百分占比',
          position: 'right',
          axisLine: { show: true, lineStyle: { color: colors[1] } },
          axisLabel: { formatter: '{value} %' },
          max: Math.ceil(Math.max(...percentages) * 1.2),
        },
      ],
      series: [
        { name: '设备数量', type: 'bar', data: deviceCounts },
        {
          name: '百分占比',
          type: 'line',
          yAxisIndex: 1,
          data: percentages,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3 },
        },
      ],
    };

    try {
      deviceChart.setOption(option);
      deviceChart.hideLoading();
    } catch (error) {
      console.error('设备图表更新失败:', error);
    }
  };

  const initDeviceChart = () => {
    if (!deviceChartRef.value) return;

    if (deviceChart) {
      return;
    }

    if (deviceChartRef.value.clientWidth === 0 || deviceChartRef.value.clientHeight === 0) {
      if (deviceChartRetryCount >= maxRetryCount) {
        // 容器可能仍处于隐藏状态，延迟后再试，避免永久放弃初始化。
        deviceChartRetryCount = 0;
        deviceChartRetryTimer = setTimeout(() => {
          initDeviceChart();
        }, 1500);
        return;
      }
      deviceChartRetryCount += 1;
      deviceChartRetryTimer = setTimeout(() => {
        initDeviceChart();
      }, 500);
      return;
    }

    deviceChartRetryCount = 0;
    deviceChart = echarts.init(deviceChartRef.value);
    deviceChart.showLoading();

    if (Object.keys(countryStats.value).length > 0) {
      updateDeviceChart();
    }
  };

  const updateStationChart = () => {
    if (!stationChart) return;

    const pieData = Object.entries(stationCountByCountry.value)
      .sort((a, b) => b[1] - a[1])
      .map(([country, count]) => ({ name: getChineseCountryName(country), value: count }));

    const option = {
      title: { left: 'center', textStyle: { color: '#333' } },
      tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} 个 ({d}%)' },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
        type: 'scroll',
        pageIconSize: 12,
        pageTextStyle: { color: '#888' },
      },
      series: [
        {
          name: '地面站分布',
          type: 'pie',
          radius: '55%',
          center: ['60%', '50%'],
          data: pieData,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
          label: { formatter: '{b}: {c} 个 ({d}%)' },
        },
      ],
    };

    stationChart.setOption(option);
    stationChart.hideLoading();
  };

  const initStationChart = () => {
    if (!stationChartRef.value) return;

    if (stationChart) {
      return;
    }

    if (stationChartRef.value.clientWidth === 0 || stationChartRef.value.clientHeight === 0) {
      if (stationChartRetryCount >= maxRetryCount) {
        // 容器可能仍处于隐藏状态，延迟后再试，避免永久放弃初始化。
        stationChartRetryCount = 0;
        stationChartRetryTimer = setTimeout(() => {
          initStationChart();
        }, 1500);
        return;
      }
      stationChartRetryCount += 1;
      stationChartRetryTimer = setTimeout(() => {
        initStationChart();
      }, 500);
      return;
    }

    stationChartRetryCount = 0;
    stationChart = echarts.init(stationChartRef.value);
    stationChart.showLoading();
    updateStationChart();
  };

  const updatePopChart = () => {
    if (!popChart) {
      initPopChart();
      return;
    }

    const popCountries = Object.entries(popCountByCountry.value)
      .sort((a, b) => b[1] - a[1])
      .map(([country, count]) => [getPopCountryChineseName(country), count]);

    if (popCountries.length === 0) {
      popChart.setOption({ title: { left: 'center', textStyle: { color: '#333' } } });
      popChart.hideLoading();
      return;
    }

    const option = {
      title: { left: 'center', top: '5%', textStyle: { color: '#333' } },
      tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
      series: [
        {
          name: 'POP点数量',
          type: 'pie',
          radius: '50%',
          center: ['50%', '55%'],
          data: popCountries.map(([country, count]) => ({ name: country, value: count })),
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
          label: { formatter: '{b}: {c} 个', overflow: 'truncate', ellipsis: '...' },
          labelLine: { length: 15, length2: 10, smooth: true },
          avoidLabelOverlap: true,
          labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
        },
      ],
    };

    try {
      popChart.setOption(option);
      popChart.hideLoading();
    } catch (error) {
      console.error('POP 图表更新失败:', error);
    }
  };

  const initPopChart = () => {
    if (!popChartRef.value) return;

    if (popChart) {
      return;
    }

    if (popChartRef.value.clientWidth === 0 || popChartRef.value.clientHeight === 0) {
      if (popChartRetryCount >= maxRetryCount) {
        // 容器可能仍处于隐藏状态，延迟后再试，避免永久放弃初始化。
        popChartRetryCount = 0;
        popChartRetryTimer = setTimeout(() => {
          initPopChart();
        }, 1500);
        return;
      }
      popChartRetryCount += 1;
      popChartRetryTimer = setTimeout(() => {
        initPopChart();
      }, 500);
      return;
    }

    popChartRetryCount = 0;
    popChart = echarts.init(popChartRef.value);
    popChart.showLoading();
    updatePopChart();
  };

  return {
    initDeviceChart,
    updateDeviceChart,
    initStationChart,
    updateStationChart,
    initPopChart,
    updatePopChart,
    resizeTerminalCharts,
    disposeTerminalCharts,
    resetTerminalChartRetries,
  };
}
