function qImg = verify_quantization(rgbImg, nColors)
    % K-means 颜色量化
    [h, w, ~] = size(rgbImg);
    X = reshape(rgbImg, [], 3);
    [idx, C] = kmeans(double(X), nColors, 'Replicates', 3, 'Verbose', 0);
    qX = C(idx, :);
    qImg = reshape(uint8(round(qX)), h, w, 3);
end