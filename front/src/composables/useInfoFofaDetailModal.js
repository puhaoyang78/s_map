import { ref } from 'vue';

export function useInfoFofaDetailModal() {
  const fofaDetailVisible = ref(false);
  const selectedFofaItem = ref(null);

  const viewFofaDetail = (item) => {
    selectedFofaItem.value = item;
    fofaDetailVisible.value = true;
  };

  const closeFofaDetail = () => {
    fofaDetailVisible.value = false;
  };

  return {
    fofaDetailVisible,
    selectedFofaItem,
    viewFofaDetail,
    closeFofaDetail,
  };
}
