export function useInfoIpv4Charts(deps) {
  const {
    echarts,
    ipSegmentChartRef,
    ipCountChartRef,
    cidrDistChartRef,
    rawIpData,
  } = deps;

  let ipSegmentChart = null;
  let ipCountChart = null;
  let cidrDistChart = null;

  const initIpSegmentChart = () => {
    if (!ipSegmentChartRef.value) return;

    if (ipSegmentChart) {
      ipSegmentChart.dispose();
    }

    ipSegmentChart = echarts.init(ipSegmentChartRef.value);

    const cidrSegments = {};
    rawIpData.value.forEach((item) => {
      if (item.cidr) {
        const cidrKey = `/${item.cidr}`;
        cidrSegments[cidrKey] = (cidrSegments[cidrKey] || 0) + 1;
      }
    });

    const sortedData = Object.entries(cidrSegments)
      .sort((a, b) => b[1] - a[1]);

    const option = {
      title: {
        text: `共 ${Object.keys(cidrSegments).length} 种 CIDR 段`,
        left: 'center',
        top: 10,
        textStyle: {
          fontSize: 14,
          color: '#666',
        },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          const data = params[0];
          return `${data.name}<br/>网段数量: ${data.value}`;
        },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: 50,
        containLabel: true,
      },
      xAxis: {
        type: 'value',
        name: '网段数量',
      },
      yAxis: {
        type: 'category',
        data: sortedData.map((item) => item[0]).reverse(),
      },
      series: [
        {
          name: '网段数量',
          type: 'bar',
          data: sortedData.map((item) => item[1]).reverse(),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#4a90e2' },
              { offset: 1, color: '#67b8ff' },
            ]),
          },
          label: {
            show: true,
            position: 'right',
            color: '#333',
            fontWeight: 'bold',
          },
        },
      ],
    };

    ipSegmentChart.setOption(option);
  };

  const initIpCountChart = () => {
    if (!ipCountChartRef.value) return;

    if (ipCountChart) {
      ipCountChart.dispose();
    }

    ipCountChart = echarts.init(ipCountChartRef.value);

    const cidrIpCounts = {};
    rawIpData.value.forEach((item) => {
      const cidrKey = `/${item.cidr}`;
      cidrIpCounts[cidrKey] = (cidrIpCounts[cidrKey] || 0) + item.ipCount;
    });

    const sortedData = Object.entries(cidrIpCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    const option = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} IPs ({d}%)',
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
        textStyle: { fontSize: 12 },
      },
      series: [
        {
          name: 'IP数量',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['60%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: {
            show: true,
            formatter: '{b}\n{d}%',
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 14,
              fontWeight: 'bold',
            },
          },
          labelLine: { show: true },
          data: sortedData.map((item) => ({
            name: item[0],
            value: item[1],
          })),
        },
      ],
    };

    ipCountChart.setOption(option);
  };

  const initCidrDistChart = () => {
    if (!cidrDistChartRef.value) return;

    if (cidrDistChart) {
      cidrDistChart.dispose();
    }

    cidrDistChart = echarts.init(cidrDistChartRef.value);

    const cidrCounts = {};
    rawIpData.value.forEach((item) => {
      const cidr = `/${item.cidr}`;
      cidrCounts[cidr] = (cidrCounts[cidr] || 0) + 1;
    });

    const sortedData = Object.entries(cidrCounts).sort((a, b) => {
      const cidrA = parseInt(a[0].substring(1));
      const cidrB = parseInt(b[0].substring(1));
      return cidrA - cidrB;
    });

    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: sortedData.map((item) => item[0]),
        axisLabel: {
          interval: 0,
          rotate: 45,
        },
      },
      yAxis: {
        type: 'value',
        name: '网段数量',
      },
      series: [
        {
          name: '数量',
          type: 'bar',
          data: sortedData.map((item) => item[1]),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#f093fb' },
              { offset: 1, color: '#f5576c' },
            ]),
          },
          label: {
            show: true,
            position: 'top',
            color: '#333',
            fontWeight: 'bold',
          },
        },
      ],
    };

    cidrDistChart.setOption(option);
  };

  const resizeIpv4Charts = () => {
    if (ipSegmentChart) ipSegmentChart.resize();
    if (ipCountChart) ipCountChart.resize();
    if (cidrDistChart) cidrDistChart.resize();
  };

  const disposeIpv4Charts = () => {
    if (ipSegmentChart) {
      ipSegmentChart.dispose();
      ipSegmentChart = null;
    }
    if (ipCountChart) {
      ipCountChart.dispose();
      ipCountChart = null;
    }
    if (cidrDistChart) {
      cidrDistChart.dispose();
      cidrDistChart = null;
    }
  };

  return {
    initIpSegmentChart,
    initIpCountChart,
    initCidrDistChart,
    resizeIpv4Charts,
    disposeIpv4Charts,
  };
}
