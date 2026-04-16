<script>
  import Header from './components/Header.svelte';
  import ChatArea from './components/ChatArea.svelte';
  import InputArea from './components/InputArea.svelte';
  import Toast from './components/Toast.svelte';
  import TrainingSpinner from './components/TrainingSpinner.svelte';
  import TrainInfoDialog from './components/TrainInfoDialog.svelte';
  import DropOverlay from './components/DropOverlay.svelte';
  import InfoPanel from './components/InfoPanel.svelte';
  import Visualizer from './components/visualizer/Visualizer.svelte';
</script>

<Header />

<div class="chat-container">
  <ChatArea />
  <InputArea />
</div>

<InfoPanel />
<Toast />
<TrainingSpinner />
<TrainInfoDialog />
<DropOverlay />
<Visualizer />

<style>
  .chat-container {
    flex: 1;
    max-width: 900px;
    width: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 0 1rem;
  }
</style>
