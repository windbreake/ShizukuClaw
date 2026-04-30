function [labels, pixelImg] = verify_slic(rgbImg, pixelSize, nIter, colorWeight)
    % rgbImg: H×W×3, uint8
    % pixelSize: 如 16
    % nIter: 如 10
    % colorWeight: 如 10

    % RGB → LAB
    labImg = rgb2lab(rgbImg);

    [h, w, ~] = size(rgbImg);
    step = pixelSize;
    nSuperpixels = round(h * w / (step * step));

    % 使用官方 SLIC
    [labels, numLabels] = superpixels(labImg, nSuperpixels, 'NumIterations', nIter, 'Compactness', colorWeight);

    % 像素化：每个超像素用平均颜色
    pixelImg = zeros(size(rgbImg), 'uint8');
    for l = 1:numLabels
        mask = labels == l;
        pixelImg(mask, :) = round(mean(rgbImg(mask, :), 1));
    end
end